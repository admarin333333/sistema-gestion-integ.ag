from datetime import datetime
from decimal import Decimal
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font
from sqlalchemy import bindparam, func, text
from sqlalchemy.orm import Session

from app.config import settings
from app.core.errors import Rechazo
from app.models.cliente import Cliente
from app.models.asiento_origen import AsientoOrigen
from app.models.factura import TIPOS_NOTA_CREDITO, Factura
from app.models.recibo import Aplicacion, Recibo, ReciboPago
from app.schemas.recibo import (
    AplicacionCrear,
    ETIQUETAS_ESTADO,
    ETIQUETAS_FORMA,
    ReciboActualizar,
    ReciboCrear,
)
from app.services import cliente_service, factura_service
from app.services.formato import pesos

# Tolerancia de centavos: los decimales flotantes no cierran exactos.
_E = 0.005


def _condiciones(cliente_id: int | None, desde, hasta) -> list:
    condiciones = []
    if cliente_id is not None:
        condiciones.append(Recibo.cliente_id == cliente_id)
    if desde:
        condiciones.append(Recibo.fecha >= desde)
    if hasta:
        condiciones.append(Recibo.fecha <= hasta)
    return condiciones


def _asientos_por_recibo(db: Session, recibo_ids: list[int]) -> dict[int, dict]:
    """Un SQL: {recibo_id: {id_asiento, estado, numero_comprobante}}.

    Igual que en facturas: una sola consulta para toda la grilla, no una por
    fila. De ahí salen los tres campos que la pantalla muestra en la columna
    "Asiento" y los botones Generar / Anular.
    """
    if not recibo_ids:
        return {}
    consulta = text(
        """
        SELECT o.id_recibo, a.id_asiento, a.estado, c.codigo_comprobante, c.numero
        FROM asiento_origen o
        JOIN asientos a ON a.id_asiento = o.id_asiento
        LEFT JOIN comprobantes_internos c ON c.id_comprobante = a.id_comprobante
        WHERE o.origen = 'RECIBO' AND o.id_recibo IN :ids
        """
    ).bindparams(bindparam("ids", expanding=True))
    filas = db.execute(consulta, {"ids": recibo_ids}).mappings().all()
    return {
        f["id_recibo"]: {
            "id_asiento": f["id_asiento"],
            "estado": f["estado"],
            "numero_comprobante": (
                f"{f['codigo_comprobante']}-{f['numero']:06d}"
                if f["codigo_comprobante"]
                else None
            ),
        }
        for f in filas
    }


def _con_asiento(db: Session, recibo: Recibo) -> Recibo:
    """Le cuelga al recibo los datos de su asiento (o None si no tiene)."""
    datos = _asientos_por_recibo(db, [recibo.id]).get(recibo.id)
    recibo.id_asiento = datos["id_asiento"] if datos else None
    recibo.estado_asiento = datos["estado"] if datos else None
    recibo.numero_comprobante_asiento = (
        datos["numero_comprobante"] if datos else None
    )
    return recibo


def listar(
    db: Session,
    cliente_id: int | None = None,
    desde=None,
    hasta=None,
    sin_asiento: bool = False,
) -> list[Recibo]:
    """Lista los recibos del filtro.

    `sin_asiento` deja solo los que todavía no entraron a los libros, que son
    los que el contador tiene que ir a asentar. Va en SQL con un NOT EXISTS, no
    filtrando en el navegador: si no, la pantalla contaría mal y el total de
    abajo no cuadraría con lo que se ve.
    """
    consulta = db.query(Recibo).filter(*_condiciones(cliente_id, desde, hasta))
    if sin_asiento:
        consulta = consulta.filter(
            ~Recibo.id.in_(
                db.query(AsientoOrigen.id_recibo).filter(
                    AsientoOrigen.origen == "RECIBO",
                    AsientoOrigen.id_recibo.isnot(None),
                )
            )
        )
    recibos = consulta.order_by(Recibo.fecha.desc(), Recibo.id.desc()).all()
    if recibos:
        asientos = _asientos_por_recibo(db, [r.id for r in recibos])
        for r in recibos:
            a = asientos.get(r.id)
            r.id_asiento = a["id_asiento"] if a else None
            r.estado_asiento = a["estado"] if a else None
            r.numero_comprobante_asiento = (
                a["numero_comprobante"] if a else None
            )
    return recibos


def total(
    db: Session,
    cliente_id: int | None = None,
    desde=None,
    hasta=None,
    sin_asiento: bool = False,
) -> float:
    """Suma de importes — se calcula SIEMPRE con SQL, nunca en el navegador.

    Solo suma los emitidos (no los anulados). `sin_asiento` tiene que aplicar
    el MISMO filtro que `listar`, o el total de abajo no cuadra con las filas que
    se ven.
    """
    consulta = db.query(Recibo).filter(*_condiciones(cliente_id, desde, hasta))
    if sin_asiento:
        consulta = consulta.filter(
            ~Recibo.id.in_(
                db.query(AsientoOrigen.id_recibo).filter(
                    AsientoOrigen.origen == "RECIBO",
                    AsientoOrigen.id_recibo.isnot(None),
                )
            )
        )
    valor = consulta.filter(Recibo.estado == "emitido").with_entities(
        func.sum(Recibo.importe)
    ).scalar()
    return float(valor or 0)


def obtener(db: Session, recibo_id: int) -> Recibo:
    recibo = db.get(Recibo, recibo_id)
    if recibo is None:
        raise Rechazo("No existe ese recibo", 404)
    return _con_asiento(db, recibo)


def _proximo_numero(db: Session) -> str:
    """Genera el siguiente número correlativo de recibo."""
    ultimo = (
        db.query(Recibo.numero)
        .order_by(Recibo.numero.desc())
        .first()
    )
    if ultimo and ultimo[0].isdigit():
        return str(int(ultimo[0]) + 1).zfill(8)
    return "00000001"


def _verificar_cliente(db: Session, cliente_id: int) -> None:
    """El cliente tiene que existir: si no, MySQL tira un error de FK."""
    if cliente_service.obtener(db, cliente_id) is None:
        raise Rechazo("No existe ese cliente", 404)


def _cuenta_cobro(db: Session, id_cuenta: int | None) -> int | None:
    """La cuenta donde entra la plata: la que vino, o la fija de Configuración.

    El contador dijo que es fondo fijo, así que se configura UNA vez
    (Configuración → Ejercicio y cobros) y el recibo no lo pregunta. Si algún
    día hay más de una cuenta, el recibo puede traer la suya y gana esa: cada
    recibo guarda la que usó, así que cambiar la fija después no reescribe los
    recibos viejos.

    Devuelve None si no hay ninguna de las dos: en ese caso se avisa al asentar,
    no al cargar el recibo (cargar un recibo no es asentar).
    """
    if id_cuenta is not None:
        return int(id_cuenta)

    from sqlalchemy import text

    fila = db.execute(
        text("SELECT valor FROM config_sistema WHERE clave = 'cuenta_cobro_fija'")
    ).scalar()
    if fila is None or str(fila).strip() == "":
        return None
    try:
        return int(fila)
    except (TypeError, ValueError):
        return None


def _verificar_periodo(db: Session, fecha, que: str) -> None:
    """Frena si la fecha cae en un período contable cerrado.

    Va en un `_` para que quede claro que es una guarda, no una función de
    negocio: en facturas, recibos y compras se llama en el MISMO lugar (primera
    línea de cada escritura) y tiene que decir lo mismo siempre.
    """
    from app.services import periodo_service

    periodo_service.verificar_abierto(db, fecha, que)


def crear(db: Session, datos: ReciboCrear) -> Recibo:
    _verificar_periodo(db, datos.fecha, "cargar un recibo con esa fecha")
    _verificar_cliente(db, datos.cliente_id)
    # El número se genera siempre solo (ver `ReciboCrear`). Antes se aceptaba
    # el que mandaba el usuario y se ignoraba en silencio, que es peor: uno
    # creía estar eligiendo el número y no pasaba nada.
    if datos.numero is not None:
        raise Rechazo(
            "El número del recibo se genera solo. Dejalo vacío en el "
            "formulario (no lo cargues a mano).",
            400,
        )
    numero = _proximo_numero(db)
    # `pagos` y `facturas` NO van a la tabla `recibos`: los pagos se guardan
    # aparte con `_guardar_pagos` y las facturas son aplicaciones. Por eso se
    # sacan del dict antes de armar el Recibo, o el constructor revienta con
    # "invalid keyword argument".
    pagos = datos.pagos or []
    facturas = datos.facturas or []
    datos_dict = datos.model_dump()
    datos_dict.pop("pagos", None)
    datos_dict.pop("facturas", None)
    datos_dict["numero"] = numero
    datos_dict["cuenta_cobro_id"] = _cuenta_cobro(db, datos.cuenta_cobro_id)
    recibo = Recibo(**datos_dict)
    db.add(recibo)
    db.flush()
    _guardar_pagos(db, recibo, pagos)

    # Aplicar a las facturas tildadas. El reparto es el MISMO que se mostró en
    # la vista previa (`_repartir_entre_facturas`), así que lo que se vio es
    # exactamente lo que queda guardado.
    tocadas = []
    if facturas:
        for r in _repartir_entre_facturas(
            db, recibo.cliente_id, facturas, recibo.importe
        ):
            db.add(
                Aplicacion(
                    recibo_id=recibo.id,
                    factura_id=r["factura_id"],
                    importe=r["importe"],
                )
            )
            tocadas.append(r["factura_id"])
    db.commit()
    db.refresh(recibo)

    # Los estados ("parcial" → "pagada") los recalcula el backend con SUM, y
    # cada uno hace su propio commit.
    for factura_id in tocadas:
        factura_service.recalcular_estado(db, factura_id)
    return recibo


def _guardar_pagos(db: Session, recibo: Recibo, pagos: list) -> None:
    """Deja los pagos del recibo como quedaron.

    Reemplaza los anteriores en vez de agregar: la pantalla manda la lista
    completa cada vez que el contador aprieta "agregar forma de pago" o saca una,
    así que guardar es "sustituir la lista entera".
    """
    recibo.pagos.clear()
    for p in pagos:
        recibo.pagos.append(
            ReciboPago(
                forma_pago=p.forma_pago,
                importe=p.importe,
                cuenta_id=p.cuenta_id,
                detalle=p.detalle,
            )
        )
    db.flush()


def cuentas_ingreso(db: Session) -> list[dict]:
    """Las cuentas donde puede ENTRAR la plata: las de "Caja y bancos".

    No sirve la lista completa del plan de cuentas: una de las 200 es "5.1.01
    costo por venta", y nadie deposita un cheque ahí. Sale el grupo "1.1.01
    Caja y bancos" (sus hijos y nietos) más las que estén marcadas con auxiliar
    BANCO, por si el estudio tiene bancos en otro lado del plan.

    Va en el backend porque el filtro es contable, no de formato: si el estudio
    agrega una cuenta de tesorería, aparece sola y sin tocar el frontend.
    """
    filas = db.execute(
        text(
            """
            SELECT p.id_cuenta, p.codigo, p.nombre
              FROM plan_cuentas p
             WHERE p.imputable = 1
               AND (
                     p.tipo_auxiliar = 'BANCO'
                  OR p.cuenta_padre_id IN (
                         SELECT id_cuenta FROM plan_cuentas WHERE codigo = '1.1.01'
                     )
                   )
             ORDER BY p.codigo
            """
        )
    ).mappings().all()
    return [dict(f) for f in filas]


def _repartir_entre_facturas(
    db: Session, cliente_id: int, factura_ids: list[int], importe
) -> list[dict]:
    """Reparte el importe del recibo entre las facturas tildadas, de la más vieja
    a la más nueva, sin pasarse del saldo de ninguna.

    Va en el BACKEND a propósito: el reparto es aritmética contable (si el
    cliente paga 700 y debe 300 de una factura y 500 de otra, se pagan 300 y 400),
    y si lo hiciera el navegador cada pantalla lo calcularía a su manera.

    Devuelve [{factura_id, importe, saldo, factura}] con lo que va a cada una.
    """
    if not factura_ids:
        return []
    _verificar_cliente(db, cliente_id)
    disponible = Decimal(str(importe))
    reparto: list[dict] = []
    # De la más vieja a la más nueva: si el cliente paga a cuenta, lo natural es
    # que salde primero lo que más días debe.
    facturas = (
        db.query(Factura)
        .filter(Factura.id.in_(factura_ids))
        .order_by(Factura.fecha, Factura.id)
        .all()
    )
    if len(facturas) != len(set(factura_ids)):
        raise Rechazo("Alguna de las facturas elegidas no existe", 404)

    for factura in facturas:
        if factura.cliente_id != cliente_id:
            raise Rechazo(
                f"La factura {factura.punto_venta}-{factura.numero} es de otro "
                "cliente: no se puede cobrar junto con este recibo.",
                400,
            )
        if factura.estado == "anulada":
            raise Rechazo(
                f"La factura {factura.punto_venta}-{factura.numero} está anulada",
                400,
            )
        if factura.tipo_comprobante in TIPOS_NOTA_CREDITO:
            raise Rechazo(
                "Las notas de crédito no se cobran: son un crédito a favor del "
                "cliente. Desmarcá esa fila.",
                400,
            )
        saldo = Decimal(str(factura_service.saldo_pendiente(db, factura.id)))
        if saldo <= _E:
            continue
        # El saldo viene como Decimal (el importe se guarda con 2 decimales) y
        # `disponible` también: si se mezclaran float y Decimal, el `-=` de más
        # abajo peta con "unsupported operand type(s) for -=".
        toma = min(saldo, disponible)
        if toma <= _E:
            break
        reparto.append(
            {"factura_id": factura.id, "importe": float(toma),
             "saldo": float(saldo), "factura": factura}
        )
        disponible -= toma
    return reparto


def previsualizar_cobro(db: Session, datos) -> dict:
    """Arma el recibo y su asiento **sin guardar nada**, para verlo antes de OK.

    Es la función que usa la pantalla en el paso "visualizar". Lo que devuelve
    es exactamente lo que se va a guardar: el reparto entre facturas sale de
    `_repartir_entre_facturas` (la misma que usa el alta) y el asiento sale de
    `asiento_automatico.proyectar_cobranza` (la misma que genera el real).
    """
    from app.services import asiento_automatico

    _verificar_cliente(db, datos.cliente_id)
    reparto = _repartir_entre_facturas(
        db, datos.cliente_id, datos.facturas or [], datos.importe
    )
    cliente = db.get(Cliente, datos.cliente_id)

    # El número todavía no existe (se genera al confirmar). Va como "tentativo"
    # para que el contador vea cómo va a quedar el concepto.
    numero = "s/n"

    avisos = []
    total_reparto = sum(r["importe"] for r in reparto)
    sin_aplicar = float(datos.importe) - round(total_reparto, 2)
    if abs(sin_aplicar) > _E and reparto:
        avisos.append(
            f"El importe del recibo es {pesos(float(datos.importe))} pero las "
            f"facturas tildadas solo admiten {pesos(round(total_reparto, 2))}. "
            f"Quedaría {pesos(sin_aplicar)} sin aplicar."
        )

    pagos = [
        {"forma_pago": p.forma_pago, "importe": float(p.importe),
         "cuenta_id": p.cuenta_id}
        for p in (datos.pagos or [])
    ]
    suma_pagos = sum(p["importe"] for p in pagos)
    if pagos and abs(suma_pagos - float(datos.importe)) > _E:
        avisos.append(
            f"Los pagos suman {pesos(suma_pagos)} y el recibo es de "
            f"{pesos(float(datos.importe))}. Revisá los importes."
        )
    if not pagos:
        avisos.append("No cargaste ninguna forma de pago: elegí con qué se cobró.")

    asiento = None
    try:
        p = asiento_automatico.proyectar_cobranza(
            db,
            numero=numero,
            cliente_nombre=cliente.nombre_completo,
            total=datos.importe,
            pagos=pagos,
            aplicaciones=[{"factura_id": r["factura_id"], "importe": r["importe"]}
                          for r in reparto],
        )
        asiento = {
            "lineas": [
                {
                    "codigo": l["codigo"],
                    "nombre_cuenta": l["nombre_cuenta"],
                    "debe": float(l["debe"]),
                    "haber": float(l["haber"]),
                    "auxiliar": (
                        l["detalle"] if l.get("detalle")
                        else (l.get("tipo_auxiliar") or "")
                    ),
                }
                for l in p["lineas"]
            ],
            "concepto": p["concepto"],
            "total_debe": float(p["total_debe"]),
            "total_haber": float(p["total_haber"]),
            "cerrado": p["cerrado"],
            "codigo_comprobante": p["codigo_comprobante"],
        }
    except Rechazo as e:
        # En la vista previa no cortamos la pantalla: el contador tiene que ver
        # el recibo igual, con el aviso de por qué el asiento no saldría.
        avisos.append(str(e))

    return {
        "numero": numero,
        "cliente_id": datos.cliente_id,
        "cliente_nombre": cliente.nombre_completo,
        "fecha": datos.fecha,
        "importe": float(datos.importe),
        "facturas": [
            {
                "id": r["factura_id"],
                "tipo_comprobante": r["factura"].tipo_comprobante,
                "punto_venta": r["factura"].punto_venta,
                "numero": r["factura"].numero,
                "concepto": r["factura"].concepto,
                "saldo": r["saldo"],
                "a_aplicar": r["importe"],
            }
            for r in reparto
        ],
        "total_aplicado": round(total_reparto, 2),
        "pagos": pagos,
        "asiento": asiento,
        "avisos": avisos,
    }


def formas_pago(db: Session) -> list[dict]:
    """Qué cuenta va por forma de pago, con el código y el nombre resueltos.

    Sale de `config_cuentas_forma_pago` en UNA consulta con LEFT JOINs: la
    pantalla no tiene que ir a buscar cada cuenta por separado.

    Las de `requiere_banco = true` vienen con `cuenta_id` en NULL, porque no
    hay una cuenta fija: el contador tiene que elegir el banco. La pantalla
    muestra el desplegable solo en esas.
    """
    filas = db.execute(
        text(
            "SELECT c.forma_pago, c.cuenta_id, c.requiere_banco, c.descripcion, "
            "       p.codigo, p.nombre "
            "  FROM config_cuentas_forma_pago c "
            "  LEFT JOIN plan_cuentas p ON p.id_cuenta = c.cuenta_id "
            " ORDER BY c.requiere_banco, c.forma_pago"
        )
    ).mappings().all()
    salida = []
    for f in filas:
        item = dict(f)
        item["cuenta_codigo"] = item.pop("codigo", None)
        item["cuenta_nombre"] = item.pop("nombre", None)
        salida.append(item)
    return salida


def guardar_pagos(db: Session, recibo_id: int, pagos: list) -> Recibo:
    """Reemplaza los pagos de un recibo que ya existe.

    Se usa cuando el contador carga los pagos aparte (por ejemplo, después de
    crear el recibo y antes de aplicarlo a las facturas).

    No se puede cambiar si el recibo ya tiene asiento: el asiento es documento
    contable, y sus líneas son la foto de estos pagos. Se anula y se genera
    otro, como con las facturas.
    """
    recibo = obtener(db, recibo_id)
    _verificar_periodo(db, recibo.fecha, "cambiar los pagos de ese recibo")
    if recibo.estado == "anulado":
        raise Rechazo("El recibo está anulado: no se le cambian los pagos", 400)
    if recibo.id_asiento:
        raise Rechazo(
            f"El recibo ya tiene el asiento {recibo.numero_comprobante_asiento}, "
            "que ya está contabilizado. Anulá ese asiento antes de cambiar los "
            "pagos.",
            409,
        )
    _guardar_pagos(db, recibo, pagos)
    db.commit()
    db.refresh(recibo)
    return recibo


def actualizar(db: Session, recibo_id: int, datos: ReciboActualizar) -> Recibo:
    recibo = obtener(db, recibo_id)
    _verificar_periodo(db, recibo.fecha, "modificar ese recibo")
    # No permitir cambiar el número
    if recibo.estado == "anulado":
        raise Rechazo("No se puede modificar un recibo anulado", 409)
    aplicado = _suma(db, Aplicacion.recibo_id == recibo_id)
    if datos.importe is not None and aplicado + _E > float(datos.importe):
        raise Rechazo(
            f"Ya aplicaste ${aplicado:,.2f} de este recibo: no podés bajar el importe",
            409,
        )
    for campo, valor in datos.model_dump(exclude_unset=True).items():
        if campo != "numero":  # Nunca permitir cambiar el número
            setattr(recibo, campo, valor)
    recibo.actualizado = datetime.utcnow()
    db.commit()
    db.refresh(recibo)
    return recibo


def anular(db: Session, recibo_id: int) -> Recibo:
    """Solo admin (el rol se controla en el router)."""
    recibo = obtener(db, recibo_id)
    _verificar_periodo(db, recibo.fecha, "anular ese recibo")
    if recibo.estado == "anulado":
        raise Rechazo("El recibo ya está anulado", 409)
    # Desaplicar todas las aplicaciones antes de anular
    aplicaciones = db.query(Aplicacion).filter(Aplicacion.recibo_id == recibo_id).all()
    for app in aplicaciones:
        factura_id = app.factura_id
        db.delete(app)
        factura_service.recalcular_estado(db, factura_id)
    recibo.estado = "anulado"
    recibo.actualizado = datetime.utcnow()
    db.commit()
    db.refresh(recibo)
    return recibo


def reabrir(db: Session, recibo_id: int) -> Recibo:
    recibo = obtener(db, recibo_id)
    _verificar_periodo(db, recibo.fecha, "reabrir ese recibo")
    if recibo.estado == "emitido":
        raise Rechazo("El recibo ya está emitido", 409)
    recibo.estado = "emitido"
    recibo.actualizado = datetime.utcnow()
    db.commit()
    db.refresh(recibo)
    return recibo


def eliminar(db: Session, recibo_id: int) -> None:
    recibo = obtener(db, recibo_id)
    _verificar_periodo(db, recibo.fecha, "eliminar ese recibo")
    if recibo.estado == "anulado":
        raise Rechazo("No se puede eliminar un recibo anulado. Reabrílo primero.", 409)
    if _suma(db, Aplicacion.recibo_id == recibo_id) > 0:
        raise Rechazo(
            "No se puede eliminar: el recibo ya está aplicado a facturas. "
            "Desaplicá esas aplicaciones primero.",
            409,
        )
    db.delete(recibo)
    db.commit()


# ------------------------------------------------------------ aplicaciones

def _suma(db: Session, *condiciones) -> float:
    valor = (
        db.query(func.coalesce(func.sum(Aplicacion.importe), 0))
        .filter(*condiciones)
        .scalar()
    )
    return float(valor)


def aplicaciones(db: Session, recibo_id: int) -> list[Aplicacion]:
    obtener(db, recibo_id)
    return (
        db.query(Aplicacion)
        .filter(Aplicacion.recibo_id == recibo_id)
        .order_by(Aplicacion.id)
        .all()
    )


def aplicar(db: Session, recibo_id: int, datos: AplicacionCrear) -> Aplicacion:
    recibo = obtener(db, recibo_id)
    factura = db.get(Factura, datos.factura_id)
    if factura is None:
        raise Rechazo("No existe esa factura", 404)
    if factura.cliente_id != recibo.cliente_id:
        raise Rechazo("El recibo y la factura son de clientes distintos", 409)
    if factura.estado == "anulada":
        raise Rechazo("No se le puede aplicar un pago a una factura anulada", 409)

    libre_recibo = float(recibo.importe) - _suma(db, Aplicacion.recibo_id == recibo_id)
    if datos.importe > libre_recibo + _E:
        raise Rechazo(
            f"El recibo {recibo.numero} solo tiene ${libre_recibo:,.2f} sin aplicar",
            409,
        )

    libre_factura = float(factura.importe) - _suma(
        db, Aplicacion.factura_id == factura.id
    )
    if datos.importe > libre_factura + _E:
        raise Rechazo(
            f"La factura solo admite ${libre_factura:,.2f} más de pago",
            409,
        )

    existe = (
        db.query(Aplicacion)
        .filter(
            Aplicacion.recibo_id == recibo_id,
            Aplicacion.factura_id == factura.id,
        )
        .first()
    )
    if existe:
        raise Rechazo("Ese recibo ya está aplicado a esa factura", 409)

    aplicacion = Aplicacion(
        recibo_id=recibo_id, factura_id=factura.id, importe=datos.importe
    )
    db.add(aplicacion)
    db.commit()
    db.refresh(aplicacion)
    factura_service.recalcular_estado(db, factura.id)
    return aplicacion


def desaplicar(db: Session, aplicacion_id: int) -> None:
    aplicacion = db.get(Aplicacion, aplicacion_id)
    if aplicacion is None:
        raise Rechazo("No existe esa aplicación", 404)
    factura_id = aplicacion.factura_id
    db.delete(aplicacion)
    db.commit()
    factura_service.recalcular_estado(db, factura_id)


# --------------------------------------------------------------------- Excel

def informe_excel(recibos: list[Recibo], total_recibido: float) -> bytes:
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Recibos"

    columnas = [
        ("Fecha", 12),
        ("Número", 12),
        ("Cliente", 30),
        ("Forma de pago", 20),
        ("Importe", 14),
    ]
    hoja.append([settings.nombre_estudio])
    hoja.cell(row=1, column=1).font = Font(bold=True, size=13)
    hoja.append([])

    hoja.append([nombre for nombre, _ in columnas])
    for celda in hoja[3]:
        celda.font = Font(bold=True)

    for r in recibos:
        hoja.append(
            [
                r.fecha.isoformat(),
                r.numero,
                r.cliente_nombre,
                ETIQUETAS_FORMA.get(r.forma_pago, r.forma_pago),
                float(r.importe),
            ]
        )

    hoja.append([""] * len(columnas))
    hoja.append(["", "", "", "TOTAL", total_recibido])
    ultima = hoja.max_row
    hoja.cell(row=ultima, column=4).font = Font(bold=True)
    celda_total = hoja.cell(row=ultima, column=5)
    celda_total.font = Font(bold=True)
    celda_total.number_format = "#,##0.00"

    for (nombre, ancho), letra in zip(columnas, "ABCDE"):
        hoja.column_dimensions[letra].width = ancho

    salida = BytesIO()
    libro.save(salida)
    return salida.getvalue()
