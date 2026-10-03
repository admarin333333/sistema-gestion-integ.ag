"""Generación automática de asientos a partir de facturas y recibos.

Conecta el módulo de facturación con el motor contable:

- Al cargar una **factura** se genera un asiento de venta.
- Al **aplicar un recibo** a una factura se genera un asiento de cobranza.

Qué cuenta va en cada lado NO está escrito acá: sale de `config_asientos`, que
es una tabla editable. Así, cambiar "Documentos a cobrar" por "Clientes" es un
cambio de datos, no de código.

Dos reglas que no se negocian:

1. **Una factura no se asienta dos veces.** Lo garantiza el UNIQUE
   (origen, id_factura) de `asiento_origen`.
2. **Si la factura o el recibo se anulan, su asiento también.** Si no, queda
   un movimiento fantasma en los libros.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import Rechazo
from app.models.asiento import Asiento, AsientoDetalle
from app.models.comprobante_interno import ComprobanteInterno
from app.models.compra import Compra
from app.models.factura import Factura
from app.models.plan_cuenta import PlanCuenta
from app.models.recibo import Aplicacion, Recibo
from app.services import asiento_service
from app.services.formato import pesos
from app.services.plan_cuenta_service import obtener as obtener_cuenta

# Cómo se llama el tipo de operación en la factura vs. en la configuración.
OPERACIONES = {"SERVICIOS": "SERVICIOS", "ARTICULOS": "ARTICULOS"}

# Los 9 tipos de comprobante se agrupan en 3 FAMILIAS, porque son 3 asientos
# distintos y no 9:
#
#   - `factura_a/b/c`      -> VENTA:   DEBE documentos / HABER ingresos
#   - `nota_credito_a/b/c` -> CREDITO: al revés, HABER documentos / DEBE ingresos
#   - `nota_debito_a/b/c`  -> DEBITO:  HABER documentos / DEBE ingresos
#
# La A, B o C dice ante QUIÉN se emitió (fiscalidad), no qué pasa
# contablemente. Por eso la numeración no se multiplica por tres: la primera
# nota de crédito es `NC-000001` sea A, B o C.
#
# Esto antes estaba roto: `proyectar_venta` armaba SIEMPRE el asiento de venta
# y el código interno salía de `origen = 'FACTURA'`, así que una nota de crédito
# tomaba un número de `FV` y se asentaba como si fuera una venta más.
FAMILIAS_TIPO = {
    "factura_a": "VENTA",
    "factura_b": "VENTA",
    "factura_c": "VENTA",
    "nota_credito_a": "CREDITO",
    "nota_credito_b": "CREDITO",
    "nota_credito_c": "CREDITO",
    "nota_debito_a": "DEBITO",
    "nota_debito_b": "DEBITO",
    "nota_debito_c": "DEBITO",
}


def familia_de(tipo_comprobante: str) -> str:
    """Devuelve VENTA, CREDITO o DEBITO. Si el tipo no se conoce, es venta.

    Sale de `FAMILIAS_TIPO` y no de `startswith`, porque "nota_debito" y
    "nota_credito" arrancan igual y se distinguen recién en el medio.
    """
    return FAMILIAS_TIPO.get(tipo_comprobante, "VENTA")


def es_nota(tipo_comprobante: str) -> bool:
    return familia_de(tipo_comprobante) in ("CREDITO", "DEBITO")


def _etiqueta_tipo(tipo_comprobante: str) -> str:
    """El nombre que va al principio del concepto del asiento.

    Sale de las etiquetas del schema para que el concepto diga "Nota de crédito
    A" y no "Nota De Credito A" (que es lo que salía con `.title()`).
    """
    from app.schemas.factura import ETIQUETAS_TIPO

    return ETIQUETAS_TIPO.get(tipo_comprobante, tipo_comprobante.replace("_", " ").title())


def _etiqueta_forma(forma: str) -> str:
    """El nombre que se ve de cada forma de pago (para el concepto del asiento)."""
    from app.schemas.recibo import ETIQUETAS_FORMA

    return ETIQUETAS_FORMA.get(forma, forma.replace("_", " "))


def _codigo_del_origen(db: Session, origen: str) -> str | None:
    """Busca en `config_comprobantes` el código que corresponde a un origen."""
    from sqlalchemy import text

    return db.execute(
        text(
            "SELECT codigo FROM config_comprobantes "
            "WHERE origen = :o AND activa = 1 LIMIT 1"
        ),
        {"o": origen},
    ).scalar()


def _codigo_de_familia(db: Session, familia: str) -> str | None:
    """El código interno del comprobante para una familia de la factura.

    VENTA -> FV, CREDITO -> NC, DEBITO -> ND. Cada familia tiene SU numeración,
    que es lo que hace que una nota de crédito NO se lleve un número de factura.
    """
    from sqlalchemy import text

    codigos = {
        "VENTA": ("FV",),
        "CREDITO": ("NC",),
        "DEBITO": ("ND",),
    }[familia]
    for codigo in codigos:
        if db.execute(
            text(
                "SELECT codigo FROM config_comprobantes "
                "WHERE codigo = :c AND origen = 'FACTURA' AND activa = 1"
            ),
            {"c": codigo},
        ).scalar():
            return codigo
    return None


def _config(db: Session, clave: str) -> dict:
    """Busca la fila de `config_asientos` y la devuelve como plan de la cuenta."""
    from sqlalchemy import text

    fila = db.execute(
        text("SELECT * FROM config_asientos WHERE clave = :c AND activa = 1"),
        {"c": clave},
    ).mappings().first()
    if fila is None:
        raise Rechazo(
            f"No está configurado el asiento «{clave}». Cargar Configuración "
            "→ Asientos antes de generar movimientos.",
            400,
        )
    return dict(fila)


def _cuenta(db: Session, id_cuenta: int) -> PlanCuenta:
    """Trae la cuenta del plan como objeto, para leer tipo_auxiliar etc."""
    cuenta = db.get(PlanCuenta, int(id_cuenta))
    if cuenta is None:
        raise Rechazo(f"La cuenta {id_cuenta} no existe", 400)
    return cuenta


def _crear_comprobante(
    db: Session, codigo: str, fecha: date, concepto: str
) -> ComprobanteInterno:
    return asiento_service.crear_comprobante(db, codigo, fecha, concepto)


# =====================================================================
# VENTA: al cargar la factura
# =====================================================================

def proyectar_venta(
    db: Session,
    *,
    fecha,
    tipo_comprobante: str,
    punto_venta: str,
    numero: str,
    concepto: str | None,
    condicion_venta: str,
    tipo_operacion: str,
    importe,
    neto,
    iva,
    cliente_id: int,
) -> dict:
    """Arma el asiento de una venta **sin guardar nada**.

    Es lo mismo que va a hacer `asiento_de_venta`, pero sin escribir en la
    base: sirve para que la pantalla le muestre al contador cómo va a quedar
    el asiento ANTES de que de OK.

    Por eso vive separada: si el preview y el asiento real hicieran la cuenta
    cada uno por su lado, el preview mostraría una cosa y el asiento otra. Un
    solo lugar decide qué cuentas van y en qué lado.

    El número del comprobante va como "tentativo": es el que le tocaría si se
    confirma ahora. Puede variar si entre la previsualización y el OK alguien
    carga otra factura.

    **El tipo de comprobante decide el signo del asiento.** Una nota de crédito
    es lo OPUESTO de una factura: los ingresos van al Debe y Documentos a
    cobrar al Haber. Por eso `config_asientos` tiene claves separadas
    (`VENTA_*`, `CREDITO_*`, `DEBITO_*`) y acá se elige una según la familia
    del tipo, en vez de armar siempre el de venta.
    """
    familia = familia_de(tipo_comprobante)
    condicion = "CONTADO" if condicion_venta == "contado" else "CTA_CORRIENTE"
    operacion = tipo_operacion or "SERVICIOS"

    if familia == "VENTA":
        clave = f"VENTA_{operacion}_{condicion}"
    else:
        # Las notas no se guardan como "al contado": una nota de crédito es una
        # corrección sobre una factura que ya existe, con su propia condición.
        clave = f"{familia}_{operacion}"
    cfg = _config(db, clave)

    # --- importes ------------------------------------------------------
    if neto is None or iva is None:
        total = Decimal(str(importe))
        neto, iva = total, Decimal("0")
        aviso = (
            "No elegiste alícuota de IVA: el importe entero va a ingresos y no "
            "sale línea de IVA."
        )
    else:
        neto, iva = Decimal(str(neto)), Decimal(str(iva))
        aviso = None

    if cfg["cuenta_debe"] is None:
        raise Rechazo(f"La configuración {clave} no tiene cuenta para el Debe", 400)

    # Las CUENTAS de cada lado salen de la configuración de la familia, que ya
    # viene con el asiento invertido para las notas: en `CREDITO_*`, la cuenta
    # del Debe es Ingresos y la del Haber es Documentos a cobrar. Por eso acá no
    # hay que invertir nada: la tabla ya está puesta al revés.
    cuenta_debe = _cuenta(db, int(cfg["cuenta_debe"]))
    cuenta_ingresos = _cuenta(db, int(cfg["cuenta_haber_ingresos"]))
    cuenta_iva = (
        _cuenta(db, int(cfg["cuenta_haber_iva"]))
        if cfg["cuenta_haber_iva"] is not None
        else None
    )

    # El MONTO depende de la CUENTA, no de la posición de la línea. Esto es lo que
    # se rompió al agregar las notas:
    #
    #   - Documentos a cobrar (cuenta de CLIENTE) lleva el TOTAL (neto + iva):
    #     es la deuda del cliente e incluye el IVA.
    #   - Ingresos lleva el NETO: el IVA no es ingreso, va a su propia cuenta.
    #   - IVA a pagar lleva el IVA.
    #
    # En una VENTA, documentos cae en el Debe y queda de cabeza. En una nota de
    # crédito, documentos cae en el HABER: si se le pusiera el total a la
    # "cuenta del Debe" a ciegas, el IVA se iría con los ingresos y el asiento
    # no cerraría (121.000 de un lado contra 100.000 del otro).
    #
    # La posición de la línea cambia con la familia (en la venta la primera es
    # documentos, en la nota es ingresos); el significado de la cuenta no. Por
    # eso se decide por cuenta.
    total = neto + iva
    id_doc = (
        int(cfg["cuenta_haber_ingresos"])
        if cuenta_ingresos.tipo_auxiliar == "CLIENTE"
        else int(cfg["cuenta_debe"])
    )
    id_ing = (
        int(cfg["cuenta_debe"])
        if cuenta_ingresos.tipo_auxiliar == "CLIENTE"
        else int(cfg["cuenta_haber_ingresos"])
    )

    def _de(id_cuenta: int) -> Decimal:
        return total if id_cuenta == id_doc else neto

    def _h(id_cuenta: int) -> Decimal:
        return total if id_cuenta == id_doc else neto

    lineas = [
        {
            "id_cuenta": int(cfg["cuenta_debe"]),
            "codigo": cuenta_debe.codigo,
            "nombre_cuenta": cuenta_debe.nombre,
            "debe": _de(int(cfg["cuenta_debe"])),
            "haber": Decimal("0"),
        },
        {
            "id_cuenta": int(cfg["cuenta_haber_ingresos"]),
            "codigo": cuenta_ingresos.codigo,
            "nombre_cuenta": cuenta_ingresos.nombre,
            "debe": Decimal("0"),
            "haber": _h(int(cfg["cuenta_haber_ingresos"])),
        },
    ]
    if iva > 0 and cuenta_iva is not None:
        # La línea de IVA se pone del MISMO lado que la línea de ingresos: si
        # los ingresos se revierten (nota de crédito), el IVA se revierte con
        # ellos. Por eso el signo sale de la cuenta de ingresos, no del nombre
        # de la cuenta de IVA.
        ingresos_en_debe = (
            int(cfg["cuenta_debe"]) == id_ing
        )
        lineas.append(
            {
                "id_cuenta": cuenta_iva.id_cuenta,
                "codigo": cuenta_iva.codigo,
                "nombre_cuenta": cuenta_iva.nombre,
                "debe": iva if ingresos_en_debe else Decimal("0"),
                "haber": Decimal("0") if ingresos_en_debe else iva,
            }
        )

    # En una VENTA la línea del Debe es Documentos a cobrar y ahí va el auxiliar
    # del cliente. En una NOTA la línea del Debe es Ingresos, y el auxiliar va
    # en la OTRA línea (Documentos a cobrar quedó en el Haber). Por eso se
    # recorre línea por línea con SU cuenta, y no se setea a ciegas la primera:
    # en la nota de crédito la cuenta con cliente es la segunda.
    for linea, cuenta in ((lineas[0], cuenta_debe), (lineas[1], cuenta_ingresos)):
        if cuenta.tipo_auxiliar in ("CLIENTE", "PROVEEDOR", "BANCO"):
            linea["tipo_auxiliar"] = cuenta.tipo_auxiliar
            linea["id_auxiliar"] = (
                cliente_id if cuenta.tipo_auxiliar == "CLIENTE" else None
            )

    concepto_asiento = (
        f"{_etiqueta_tipo(tipo_comprobante)} "
        f"{punto_venta}-{numero} — {concepto or ''}"
    ).strip(" —")

    # El código interno sale de la FAMILIA: una nota de crédito toma `NC`, no
    # `FV`. Con el código de `origen = 'FACTURA'` (que es FV) las notas se
    # comían la numeración de las facturas.
    codigo = _codigo_de_familia(db, familia)
    tentativo = None
    if codigo:
        from app.services import ejercicio_service

        try:
            ejercicio = ejercicio_service.el_de_la_fecha(db, fecha)
            if ejercicio is not None:
                tentativo = (
                    f"{codigo}-"
                    f"{asiento_service._proximo_numero(db, codigo, ejercicio.id_ejercicio):06d}"
                )
        except Exception:
            tentativo = None

    # Los totales se suman de las LÍNEAS, no de `neto + iva`: si el signo de
    # alguna línea estuviera mal (que es lo que pasaba con las notas), el total
    # mostraría un número que no es el del asiento y la pantalla cerraría en
    # falso. Sumando las líneas, el preview dice la verdad.
    total_debe = sum((l["debe"] for l in lineas), Decimal("0.0000"))
    total_haber = sum((l["haber"] for l in lineas), Decimal("0.0000"))

    return {
        "fecha": fecha,
        "concepto": concepto_asiento,
        "codigo_comprobante": codigo,
        "numero_completo_tentativo": tentativo,
        "lineas": lineas,
        "total_debe": total_debe,
        "total_haber": total_haber,
        "cierra": total_debe == total_haber,
        "familia": familia,
        "aviso": aviso,
        "detalle": lineas,
    }


def asiento_de_venta(db: Session, factura_id: int) -> dict:
    """Genera el asiento de una factura. Si ya tiene uno, no hace nada."""
    factura = db.get(Factura, factura_id)
    if factura is None:
        raise Rechazo("La factura no existe", 404)

    if factura.estado == "anulada":
        raise Rechazo(
            "La factura está anulada: no se genera el asiento", 400
        )

    # ¿Ya tiene asiento? (el UNIQUE igual lo impide, pero así se avisa claro)
    if _ya_asentada(db, "FACTURA", factura_id):
        return {"generado": False, "motivo": "La factura ya tenía asiento"}

    # La MISMA proyección que se mostró en pantalla. No se recalcula acá: si
    # el preview y el asiento real hicieran la cuenta por separado, el
    # contador vería una cosa y se guardaría otra.
    p = proyectar_venta(
        db,
        fecha=factura.fecha,
        tipo_comprobante=factura.tipo_comprobante,
        punto_venta=factura.punto_venta,
        numero=factura.numero,
        concepto=factura.concepto,
        condicion_venta=factura.condicion_venta,
        tipo_operacion=factura.tipo_operacion,
        importe=factura.importe,
        neto=factura.neto,
        iva=factura.iva,
        cliente_id=factura.cliente_id,
    )
    aviso = p["aviso"]
    # La proyección trae los campos solo para mostrar; `guardar_detalle` los
    # necesita como no, así que se limpian.
    lineas = [
        {k: v for k, v in linea.items() if k in ("id_cuenta", "debe", "haber", "tipo_auxiliar", "id_auxiliar")}
        for linea in p["lineas"]
    ]
    concepto = p["concepto"]

    codigo = _codigo_de_familia(db, familia_de(factura.tipo_comprobante))
    comprobante = (
        _crear_comprobante(db, codigo, factura.fecha, concepto)
        if codigo
        else None
    )

    asiento = asiento_service.crear_asiento(
        db,
        factura.fecha,
        concepto,
        id_comprobante=comprobante.id_comprobante if comprobante else None,
    )
    # Se guarda el detalle directo (sin pasar por el endpoint) para no
    # recalcular de más, pero pasando por el mismo servicio.
    asiento_service.guardar_detalle(
        db, asiento.id_asiento, [dict(x) for x in lineas]
    )
    db.refresh(asiento)

    _insert_origen(db, asiento.id_asiento, "FACTURA", factura_id=factura_id)

    # Se contabiliza solo: una factura emitida es un hecho, no un borrador.
    asiento_service.contabilizar(db, asiento.id_asiento)

    return {
        "generado": True,
        "asiento_id": asiento.id_asiento,
        "numero_completo": (
            comprobante.numero_completo if comprobante else None
        ),
        "concepto": concepto,
        "lineas": len(lineas),
        "aviso": aviso,
    }


# =====================================================================
# COBRANZA: al aplicar un recibo
# =====================================================================

def proyectar_cobranza(
    db: Session,
    *,
    numero: str,
    cliente_nombre: str,
    total,
    pagos: list[dict],
    aplicaciones: list[dict],
    cuenta_cobro_id: int | None = None,
) -> dict:
    """Arma el asiento de cobranza **sin guardar nada**.

    Es lo mismo que va a hacer `asiento_de_cobranza`, pero sin escribir en la
    base: sirve para que la pantalla le muestre al contador cómo va a quedar el
    asiento ANTES de que confirme el recibo.

    Por eso vive separada: si el preview y el asiento real hicieran la cuenta
    cada uno por su lado, el preview mostraría una cosa y el asiento otra. Un
    solo lugar decide qué cuentas van y en qué lado.

    - `pagos`: [{forma_pago, importe, cuenta_id}] — un Debe por cada medio de
      pago. `cuenta_id` en NULL es "el contador todavía no eligió el banco".
    - `aplicaciones`: [{factura_id, importe}] — un Haber por factura a
      `Documentos a cobrar`, con el cliente como auxiliar.
    - `cuenta_cobro_id` es el CAMINO VIEJO: si no hay pagos (recibos cargados
      antes de la tabla `recibo_pagos`), el Debe va todo a esa cuenta.
    """
    # --- el Debe: uno por cada pago -------------------------------------
    if pagos:
        lineas_debe = []
        for pago in pagos:
            if pago.get("cuenta_id") is None:
                raise Rechazo(
                    f"El pago de {_etiqueta_forma(pago['forma_pago'])} no tiene "
                    "cuenta. Elegí en qué banco entró la plata antes de "
                    "generar el asiento.",
                    400,
                )
            cuenta = _cuenta(db, int(pago["cuenta_id"]))
            if not cuenta.imputable:
                raise Rechazo(
                    f"{cuenta.codigo} {cuenta.nombre} es un agrupador: "
                    "elegí una cuenta de detalle.",
                    400,
                )
            linea = {
                "id_cuenta": cuenta.id_cuenta,
                "debe": Decimal(str(pago["importe"])),
                "haber": Decimal("0"),
                "codigo": cuenta.codigo,
                "nombre_cuenta": cuenta.nombre,
            }
            if cuenta.tipo_auxiliar in ("BANCO", "CLIENTE", "PROVEEDOR"):
                linea["tipo_auxiliar"] = cuenta.tipo_auxiliar
            lineas_debe.append(linea)
    else:
        if cuenta_cobro_id is None:
            raise Rechazo(
                "El recibo no tiene pagos cargados. Elegí con qué se pagó "
                "(forma de pago y en qué cuenta) antes de generar el asiento.",
                400,
            )
        cuenta_cobro = _cuenta(db, int(cuenta_cobro_id))
        if not cuenta_cobro.imputable:
            raise Rechazo(
                f"{cuenta_cobro.codigo} {cuenta_cobro.nombre} es un agrupador: "
                "elegí una cuenta de detalle.",
                400,
            )
        linea_debe = {
            "id_cuenta": cuenta_cobro.id_cuenta,
            # En el camino viejo hay una sola línea con toda la plata.
            "debe": Decimal(str(total)),
            "haber": Decimal("0"),
            "codigo": cuenta_cobro.codigo,
            "nombre_cuenta": cuenta_cobro.nombre,
        }
        if cuenta_cobro.tipo_auxiliar in ("BANCO", "CLIENTE", "PROVEEDOR"):
            linea_debe["tipo_auxiliar"] = cuenta_cobro.tipo_auxiliar
        lineas_debe = [linea_debe]

    if not aplicaciones:
        raise Rechazo(
            "Elegí al menos una factura para cobrar: sin documentos a los que "
            "aplicar el recibo no hay nada que asentar.",
            400,
        )

    # --- el Haber: documentos a cobrar, una línea por factura aplicada ----
    cfg = _config(db, "COBRANZA")
    id_cobranza = cfg.get("cuenta_haber_cobranza")
    if id_cobranza is None:
        raise Rechazo(
            "La configuración COBRANZA no tiene la cuenta de documentos a "
            "cobrar. Cargala en Configuración → Asientos.",
            400,
        )
    cuenta_haber = _cuenta(db, int(id_cobranza))

    total_haber = Decimal("0")
    lineas_haber = []
    for ap in aplicaciones:
        factura = db.get(Factura, ap["factura_id"])
        importe = Decimal(str(ap["importe"]))
        total_haber += importe
        linea = {
            "id_cuenta": cuenta_haber.id_cuenta,
            "debe": Decimal("0"),
            "haber": importe,
            "codigo": cuenta_haber.codigo,
            "nombre_cuenta": cuenta_haber.nombre,
        }
        if cuenta_haber.tipo_auxiliar == "CLIENTE" and factura is not None:
            linea["tipo_auxiliar"] = "CLIENTE"
            linea["id_auxiliar"] = factura.cliente_id
            linea["detalle"] = (
                f"{factura.tipo_comprobante} "
                f"{factura.punto_venta}-{factura.numero}"
            )
        lineas_haber.append(linea)

    # Las líneas del Debe van PRIMERO: es la lectura natural del asiento de
    # cobranza ("entró la plata acá"), y el orden no afecta la partida doble.
    lineas = lineas_debe + lineas_haber

    # Que el Debe dé exactamente lo que va al Haber. Si no coinciden, el
    # `guardar_detalle` va a rechazar el asiento por desbalanceado y el contador
    # vería un error sin saber por qué; mejor avisar acá, con los números.
    suma_debe = sum((l["debe"] for l in lineas_debe), Decimal("0.0000"))
    if suma_debe != total_haber:
        raise Rechazo(
            f"Los pagos suman {pesos(suma_debe)} pero a las facturas se les "
            f"aplica {pesos(total_haber)}. Revisá los importes antes de generar "
            "el asiento.",
            400,
        )

    concepto = f"Recibo {numero} — {cliente_nombre}"
    if len(pagos) > 1:
        # Con varias formas de pago, el concepto dice cuáles: si el contador ve
        # "Recibo 00000067" y tres líneas en el Debe, tiene que poder saber
        # después qué fue cada una.
        medios = ", ".join(
            f"{_etiqueta_forma(p['forma_pago'])} {p['importe']}" for p in pagos
        )
        concepto = f"{concepto} ({medios})"

    return {
        "lineas": lineas,
        "concepto": concepto,
        "total_debe": suma_debe,
        "total_haber": total_haber,
        "cerrado": suma_debe == total_haber,
        "codigo_comprobante": _codigo_del_origen(db, "RECIBO"),
    }


def asiento_de_cobranza(db: Session, recibo_id: int) -> dict:
    """Genera el asiento de un recibo, con un Haber por cada factura aplicada."""
    recibo = db.get(Recibo, recibo_id)
    if recibo is None:
        raise Rechazo("El recibo no existe", 404)

    if recibo.estado == "anulado":
        raise Rechazo("El recibo está anulado: no se genera el asiento", 400)

    if _ya_asentada(db, "RECIBO", recibo_id):
        return {"generado": False, "motivo": "El recibo ya tenía asiento"}

    aplicaciones = (
        db.execute(
            select(Aplicacion)
            .where(Aplicacion.recibo_id == recibo_id)
            .order_by(Aplicacion.id)
        )
        .scalars()
        .all()
    )

    # La MISMA proyección que se mostró en pantalla (ver `proyectar_cobranza`).
    # No se recalcula acá: si el preview y el asiento real hicieran la cuenta por
    # separado, el contador vería una cosa y se guardaría otra.
    p = proyectar_cobranza(
        db,
        numero=recibo.numero,
        cliente_nombre=recibo.cliente.nombre_completo,
        total=recibo.importe,
        pagos=[
            {
                "forma_pago": pg.forma_pago,
                "importe": pg.importe,
                "cuenta_id": pg.cuenta_id,
            }
            for pg in (recibo.pagos or [])
        ],
        aplicaciones=[
            {"factura_id": ap.factura_id, "importe": ap.importe}
            for ap in aplicaciones
        ],
        cuenta_cobro_id=recibo.cuenta_cobro_id,
    )
    lineas = [
        {k: v for k, v in linea.items()
         if k in ("id_cuenta", "debe", "haber", "tipo_auxiliar", "id_auxiliar")}
        for linea in p["lineas"]
    ]
    concepto = p["concepto"]

    codigo = p["codigo_comprobante"]
    comprobante = (
        _crear_comprobante(db, codigo, recibo.fecha, concepto)
        if codigo
        else None
    )

    asiento = asiento_service.crear_asiento(
        db,
        recibo.fecha,
        concepto,
        id_comprobante=comprobante.id_comprobante if comprobante else None,
    )
    asiento_service.guardar_detalle(db, asiento.id_asiento, [dict(x) for x in lineas])
    db.refresh(asiento)

    _insert_origen(db, asiento.id_asiento, "RECIBO", recibo_id=recibo_id)
    asiento_service.contabilizar(db, asiento.id_asiento)

    return {
        "generado": True,
        "asiento_id": asiento.id_asiento,
        "numero_completo": (
            comprobante.numero_completo if comprobante else None
        ),
        "concepto": concepto,
        "facturas": len(aplicaciones),
        "total": str(p["total_haber"]),
    }


# =====================================================================
# COMPRA: al cargar la factura del proveedor
# =====================================================================

# Las dos cuentas fijas del asiento de compra. Son DEUDORAS del activo (ramas
# 1.1.05), no cuentas de IVA a pagar: el IVA que pagás a un proveedor es un
# CRÉDITO tuyo, y hasta que no lo usás contra ARCA es un activo.
#
# Se nombran por código y no en `config_asientos` a propósito: la compra tiene
# UNA sola variante (no hay "artículos" ni "al contado" como en la venta), así
# que una fila de configuración sería indirección sin contenido. La cuenta que
# SÍ cambia en cada compra —la de gasto— la elige el contador. Si algún día se
# renumera el plan, se cambian estos dos códigos acá y en ningún otro lado.
CUENTA_IVA_COMPRA = "1.1.05.04"  # IVA crédito fiscal
CUENTA_PERCEPCION_COMPRA = "1.1.05.06"  # Percepciones a favor
CUENTA_PROVEEDORES = "2.1.01.01"  # Proveedores (con auxiliar PROVEEDOR)

# La rama de GASTOS del plan: la cuenta de gasto de una compra tiene que caer
# acá adentro, si no el gasto no aparecería en el informe por centro.
CODIGO_RAIZ_GASTOS = "6"


def _cuenta_por_codigo(db: Session, codigo: str, que: str) -> PlanCuenta:
    cuenta = db.query(PlanCuenta).filter(PlanCuenta.codigo == codigo).first()
    if cuenta is None:
        raise Rechazo(
            f"El plan de cuentas no tiene la cuenta {codigo} ({que}), que el "
            "asiento de compra necesita. Revisá el plan de cuentas.",
            400,
        )
    return cuenta


def proyectar_compra(
    db: Session,
    *,
    fecha,
    tipo_comprobante: str,
    punto_venta: str,
    numero: str,
    concepto: str | None,
    neto,
    iva,
    percepcion,
    total,
    cuenta_gasto_id: int,
    proveedor_id: int,
    proveedor_nombre: str = "",
) -> dict:
    """Arma el asiento de una COMPRA **sin guardar nada**.

    Es el espejo de `proyectar_venta`: los cuatro Debes/Haberes que armaría la
    factura del proveedor, para que la pantalla le muestre al contador cómo va
    a quedar ANTES de que le dé OK. Vive acá y no en el router por la misma
    razón que la venta: preview y asiento real tienen que usar la misma función
    o se contradicen.

    El asiento:

        Debe  <cuenta de gasto>   la 6.x que eligió el contador   (neto)
        Debe  1.1.05.04 IVA crédito fiscal                          (iva)
        Debe  1.1.05.06 Percepciones a favor                   (percepción)
              Haber  2.1.01.01 Proveedores                          (total)

    El Haber de Proveedores es el **total de la compra tal cual lo calcula la
    app** (`neto + iva + percepción`). Por eso el asiento cierra con el número
    que el contador ya ve en la pantalla, sin ningún ajuste.

    La percepción NO se resta del IVA: son dos créditos distintos y por
    separado (uno contra ARCA, otro a favor del estudio). Por eso van en dos
    líneas.

    **La NOTA DE CRÉDITO es el mismo asiento al revés.** Cuando el proveedor
    devuelve mercadería, la nota no es una compra: es la baja de una compra
    anterior. Los tres Debes van al Haber y el Haber de Proveedores va al Debe,
    con la misma cuenta de gasto. Si se armara "hacia adelante", la nota sumaría
    gasto en vez de restarlo y el informe por centro mostraría más gasto del
    que hubo.

    Solo se invierte la familia CREDITO. Un DEBITO (nota de débito del
    proveedor) es un aumento de la deuda: va como la compra.
    """
    cuenta_gasto = db.get(PlanCuenta, int(cuenta_gasto_id))
    if cuenta_gasto is None:
        raise Rechazo("Elegí la cuenta de gasto del plan", 400)
    if not cuenta_gasto.imputable:
        raise Rechazo(
            f"La cuenta {cuenta_gasto.codigo} ({cuenta_gasto.nombre}) no es "
            "imputable: es un agrupador. Elegí una cuenta de gasto concreta.",
            400,
        )
    if not cuenta_gasto.codigo.startswith(CODIGO_RAIZ_GASTOS + "."):
        raise Rechazo(
            f"La cuenta {cuenta_gasto.codigo} ({cuenta_gasto.nombre}) no está "
            f"bajo {CODIGO_RAIZ_GASTOS} GASTOS. El gasto de una compra tiene que "
            "ir a una cuenta de la rama de gastos, si no no aparece en el "
            "informe por centro de costos.",
            400,
        )

    cuenta_iva = _cuenta_por_codigo(db, CUENTA_IVA_COMPRA, "IVA crédito fiscal")
    cuenta_perc = _cuenta_por_codigo(
        db, CUENTA_PERCEPCION_COMPRA, "Percepciones a favor"
    )
    cuenta_prov = _cuenta_por_codigo(db, CUENTA_PROVEEDORES, "Proveedores")

    n, i, p = Decimal(str(neto)), Decimal(str(iva)), Decimal(str(percepcion))
    # El total sale de la base, no de la suma de las líneas: si la app calcula
    # otra cosa, el asiento tiene que usar el número que el contador vio.
    t = Decimal(str(total))

    # Una nota de crédito del proveedor es la baja de una compra: el mismo
    # asiento del revés. Solo CREDITO se invierte (un DEBITO es un aumento de la
    # deuda y va como la compra).
    inverso = familia_de(tipo_comprobante) == "CREDITO"

    def linea(cuenta, monto, es_debe, aux=False):
        d = {
            "id_cuenta": cuenta.id_cuenta,
            "codigo": cuenta.codigo,
            "nombre_cuenta": cuenta.nombre,
            "debe": monto if es_debe else Decimal("0"),
            "haber": Decimal("0") if es_debe else monto,
        }
        if aux:
            d["tipo_auxiliar"] = "PROVEEDOR"
            d["id_auxiliar"] = proveedor_id
        return d

    # En el asiento normal el gasto, el IVA y la percepción van al Debe y el
    # proveedor al Haber. Invertido es al revés.
    lado_cargos = not inverso

    lineas = [linea(cuenta_gasto, n, lado_cargos)]

    aviso = None
    if i > 0:
        lineas.append(linea(cuenta_iva, i, lado_cargos))
    else:
        aviso = "La compra no tiene IVA: no sale línea de IVA crédito fiscal."
    if p > 0:
        lineas.append(linea(cuenta_perc, p, lado_cargos))

    lineas.append(linea(cuenta_prov, t, not lado_cargos, aux=True))

    codigo = _codigo_del_origen(db, "COMPRA")

    etiqueta = _etiqueta_tipo(tipo_comprobante)
    concepto_final = (
        concepto
        or f"Compra {etiqueta} {punto_venta}-{numero} — {proveedor_nombre}"
    ).strip()

    total_debe = sum((l["debe"] for l in lineas), Decimal("0"))
    total_haber = sum((l["haber"] for l in lineas), Decimal("0"))

    return {
        "fecha": fecha,
        "concepto": concepto_final,
        "codigo_comprobante": codigo,
        "numero_comprobante": None,
        "total_debe": total_debe,
        "total_haber": total_haber,
        "diferencia": total_debe - total_haber,
        "balanceado": total_debe == total_haber,
        "lineas": lineas,
        "aviso": aviso,
    }


def asiento_de_compra(db: Session, compra_id: int) -> dict:
    """Genera y contabiliza el asiento de una factura de proveedor.

    Sirve igual para las notas de crédito: la inversión la decide
    `proyectar_compra` según el tipo de comprobante, no esta función. Así el
    preview y el asiento real usan el mismo camino.

    Usa la MISMA proyección que se mostró en pantalla: si el preview y el
    asiento real hicieran la cuenta por separado, el contador vería una cosa y
    se guardaría otra.
    """
    compra = db.get(Compra, compra_id)
    if compra is None:
        raise Rechazo("La compra no existe", 404)

    if compra.estado == "anulada":
        raise Rechazo("La compra está anulada: no se genera el asiento", 400)

    if compra.cuenta_gasto_id is None:
        raise Rechazo(
            "La compra no tiene cuenta de gasto: no hay a qué debitarla. "
            "Editá la compra y elegí la cuenta del plan.",
            409,
        )

    if _ya_asentada(db, "COMPRA", compra_id):
        return {"generado": False, "motivo": "La compra ya tenía asiento"}

    p = proyectar_compra(
        db,
        fecha=compra.fecha,
        tipo_comprobante=compra.tipo_comprobante,
        punto_venta=compra.punto_venta,
        numero=compra.numero,
        concepto=compra.concepto,
        neto=compra.neto,
        iva=compra.iva,
        percepcion=compra.percepcion_iva,
        total=compra.total,
        cuenta_gasto_id=compra.cuenta_gasto_id,
        proveedor_id=compra.proveedor_id,
        proveedor_nombre=compra.proveedor.nombre_completo,
    )

    lineas = [
        {k: v for k, v in linea.items()
         if k in ("id_cuenta", "debe", "haber", "tipo_auxiliar", "id_auxiliar")}
        for linea in p["lineas"]
    ]

    comprobante = (
        _crear_comprobante(db, p["codigo_comprobante"], compra.fecha, p["concepto"])
        if p["codigo_comprobante"]
        else None
    )
    asiento = asiento_service.crear_asiento(
        db,
        compra.fecha,
        p["concepto"],
        id_comprobante=comprobante.id_comprobante if comprobante else None,
    )
    asiento_service.guardar_detalle(db, asiento.id_asiento, [dict(x) for x in lineas])
    db.refresh(asiento)

    _insert_origen(db, asiento.id_asiento, "COMPRA", compra_id=compra_id)
    asiento_service.contabilizar(db, asiento.id_asiento)

    return {
        "generado": True,
        "asiento_id": asiento.id_asiento,
        "numero_completo": (
            comprobante.numero_completo if comprobante else None
        ),
        "concepto": p["concepto"],
        "total": str(p["total_haber"]),
    }


# =====================================================================
# helpers
# =====================================================================

def _ya_asentada(db: Session, origen: str, id_origen: int) -> bool:
    from sqlalchemy import text

    columna = {
        "FACTURA": "id_factura",
        "RECIBO": "id_recibo",
        "COMPRA": "id_compra",
    }[origen]
    return bool(
        db.execute(
            text(
                "SELECT COUNT(*) FROM asiento_origen "
                f"WHERE origen = :o AND {columna} = :i"
            ),
            {"o": origen, "i": id_origen},
        ).scalar()
    )


def _insert_origen(
    db: Session,
    asiento_id: int,
    origen: str,
    factura_id=None,
    recibo_id=None,
    compra_id=None,
) -> None:
    from sqlalchemy import text

    db.execute(
        text(
            "INSERT INTO asiento_origen "
            "(id_asiento, origen, id_factura, id_recibo, id_compra) "
            "VALUES (:a, :o, :f, :r, :c)"
        ),
        {"a": asiento_id, "o": origen, "f": factura_id, "r": recibo_id, "c": compra_id},
    )
    db.commit()