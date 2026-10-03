from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from io import BytesIO
from xml.sax.saxutils import escape

from openpyxl import Workbook
from openpyxl.styles import Font
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import bindparam, func, inspect, text
from sqlalchemy.orm import Session

from app.core.errors import Rechazo
from app.models.alicuota import AlicuotaIva
from app.models.cliente import Cliente
from app.models.anticipo import AplicacionAnticipo
from app.models.factura import ESTADOS, TIPOS_NOTA_CREDITO, Factura
from app.models.recibo import Aplicacion
from app.schemas.factura import ETIQUETAS_CONDICION, ETIQUETAS_ESTADO, ETIQUETAS_TIPO
from app.schemas.factura import FacturaActualizar, FacturaCrear
from app.config import settings
from app.services.formato import pesos

# Tabla que se crea junto con los recibos (paso siguiente de la Fase 3).
# Tablas donde puede estar imputada una factura (recibos y anticipos).
TABLAS_APLICACIONES = ("aplicaciones_recibo", "aplicaciones_anticipo")

# Los montos van a 2 decimales. Los índices de moneda usan 4; acá son pesos.
_DOS = Decimal("0.01")

# Tolerancia para comparar importes. Un saldo de 0,004 pesos (por redondeos) es
# cero a efectos contables: sin esto, una factura pagada hasta el último peso
# quedaría "parcial" para siempre.
_E = 0.005


def _condiciones(cliente_id, estado, desde, hasta) -> list:
    if estado and estado not in ESTADOS:
        raise Rechazo("Estado no válido", 400)
    condiciones = []
    if cliente_id is not None:
        condiciones.append(Factura.cliente_id == cliente_id)
    if estado:
        condiciones.append(Factura.estado == estado)
    if desde:
        condiciones.append(Factura.fecha >= desde)
    if hasta:
        condiciones.append(Factura.fecha <= hasta)
    return condiciones


def _asientos_por_factura(db: Session, factura_ids: list[int]) -> dict[int, dict]:
    """Un SQL: {factura_id: {id, estado, numero}}. Los 3 campos de una vez.

    Va en una sola consulta porque la pantalla de facturas las muestra todas
    juntas; si fuera una por factura serían N consultas para pintar una grilla.
    """
    if not factura_ids:
        return {}
    consulta = text(
        """
        SELECT o.id_factura, a.id_asiento, a.estado, c.codigo_comprobante, c.numero
        FROM asiento_origen o
        JOIN asientos a ON a.id_asiento = o.id_asiento
        LEFT JOIN comprobantes_internos c ON c.id_comprobante = a.id_comprobante
        WHERE o.origen = 'FACTURA' AND o.id_factura IN :ids
        """
    ).bindparams(bindparam("ids", expanding=True))
    filas = db.execute(consulta, {"ids": factura_ids}).mappings().all()
    return {
        f["id_factura"]: {
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


def _con_asiento(db: Session, factura: Factura) -> Factura:
    """Le cuelga a la factura los datos de su asiento (o None si no tiene)."""
    datos = _asientos_por_factura(db, [factura.id]).get(factura.id)
    factura.id_asiento = datos["id_asiento"] if datos else None
    factura.estado_asiento = datos["estado"] if datos else None
    factura.numero_comprobante_asiento = datos["numero_comprobante"] if datos else None
    return factura


def listar(
    db: Session,
    cliente_id: int | None = None,
    estado: str | None = None,
    desde=None,
    hasta=None,
    descendente: bool = False,
) -> list[Factura]:
    consulta = db.query(Factura).filter(
        *_condiciones(cliente_id, estado, desde, hasta)
    )
    if descendente:
        facturas = consulta.order_by(Factura.fecha.desc(), Factura.id.desc()).all()
    else:
        facturas = consulta.order_by(Factura.fecha.asc(), Factura.id.asc()).all()

    # Calculamos lo aplicado (recibos + anticipos) para cada factura
    if facturas:
        ids = [f.id for f in facturas]
        aplicados = _aplicados_por_factura(db, ids)
        asientos = _asientos_por_factura(db, ids)
        for f in facturas:
            f.aplicado = aplicados.get(f.id, 0.0)
            a = asientos.get(f.id)
            f.id_asiento = a["id_asiento"] if a else None
            f.estado_asiento = a["estado"] if a else None
            f.numero_comprobante_asiento = a["numero_comprobante"] if a else None

    return facturas


def documentos_a_cobrar(db: Session, cliente_id: int) -> dict:
    """Qué tiene este cliente para cobrar: las facturas con saldo y las NCs.

    Es lo que muestra la pantalla del recibo para que el contador tilde. El
    saldo de cada factura YA viene descontadas las notas de crédito vinculadas
    (por eso `_creditos`), así que la pantalla no tiene que restar nada: tildar
    una factura de 1.000 con una NC de 300 da 700, que es lo que hay que cobrar.

    Todo en 2 consultas: una para las facturas (con SUM de cobrado y de
    créditos, agrupado) y una para las NC. Los totales salen de SQL.
    """
    cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    if cliente is None:
        raise Rechazo("No existe ese cliente", 404)

    filas = db.execute(
        text(
            """
            SELECT f.id, f.tipo_comprobante, f.punto_venta, f.numero, f.fecha,
                   f.importe, f.concepto, f.estado, f.factura_relacionada_id,
                   COALESCE((
                       SELECT SUM(a.importe) FROM aplicaciones_recibo a
                        WHERE a.factura_id = f.id
                   ), 0) + COALESCE((
                       SELECT SUM(p.importe) FROM aplicaciones_anticipo p
                        WHERE p.factura_id = f.id
                   ), 0) AS cobrado,
                   COALESCE((
                       SELECT SUM(n.importe) FROM facturas n
                        WHERE n.factura_relacionada_id = f.id
                          AND n.tipo_comprobante IN ('nota_credito_a',
                                                     'nota_credito_b',
                                                     'nota_credito_c')
                          AND n.estado <> 'anulada'
                   ), 0) AS creditos
              FROM facturas f
             WHERE f.cliente_id = :cid
               AND f.estado <> 'anulada'
             ORDER BY f.fecha, f.id
            """
        ),
        {"cid": cliente_id},
    ).mappings().all()

    facturas = []
    notas = []
    total_facturas = 0.0
    total_notas = 0.0

    for f in filas:
        es_credito = f["tipo_comprobante"] in TIPOS_NOTA_CREDITO
        item = {
            "id": f["id"],
            "tipo_comprobante": f["tipo_comprobante"],
            "etiqueta_tipo": ETIQUETAS_TIPO.get(
                f["tipo_comprobante"], f["tipo_comprobante"]
            ),
            "punto_venta": f["punto_venta"],
            "numero": f["numero"],
            "fecha": f["fecha"].isoformat() if hasattr(f["fecha"], "isoformat")
            else str(f["fecha"]),
            "concepto": f["concepto"],
            "importe": float(f["importe"]),
            "estado": f["estado"],
            "es_credito": es_credito,
            "factura_relacionada_id": f["factura_relacionada_id"],
        }
        if es_credito:
            item["cobrado"] = float(f["cobrado"])
            item["creditos"] = 0.0
            item["saldo"] = 0.0
            notas.append(item)
            total_notas += item["importe"]
        else:
            cobrado = float(f["cobrado"])
            creditos = float(f["creditos"])
            saldo = item["importe"] - creditos - cobrado
            item["cobrado"] = round(cobrado, 2)
            item["creditos"] = round(creditos, 2)
            item["saldo"] = round(saldo, 2)
            # Solo las que todavía deben algo. Una factura ya cubierta por NC o
            # por cobros no aparece para que no se tilde por error.
            if saldo > _E:
                facturas.append(item)
                total_facturas += saldo

    return {
        "cliente_id": cliente_id,
        "cliente_nombre": cliente.nombre_completo,
        "facturas": facturas,
        "notas_credito": notas,
        "total_facturas": round(total_facturas, 2),
        "total_notas": round(total_notas, 2),
        # Lo que hay que cobrar ahora. Las NC vinculadas YA están restadas en
        # `total_facturas`, así que acá no se vuelven a descontar: sumarlas otra
        # vez descontaría dos veces.
        "saldo": round(total_facturas, 2),
    }


def _aplicados_por_factura(db: Session, factura_ids: list[int]) -> dict[int, float]:
    """Devuelve dict {factura_id: total_aplicado} sumando recibos + anticipos."""
    if not factura_ids:
        return {}
    por_recibos = dict(
        db.query(Aplicacion.factura_id, func.coalesce(func.sum(Aplicacion.importe), 0))
        .filter(Aplicacion.factura_id.in_(factura_ids))
        .group_by(Aplicacion.factura_id)
        .all()
    )
    por_anticipos = dict(
        db.query(AplicacionAnticipo.factura_id, func.coalesce(func.sum(AplicacionAnticipo.importe), 0))
        .filter(AplicacionAnticipo.factura_id.in_(factura_ids))
        .group_by(AplicacionAnticipo.factura_id)
        .all()
    )
    resultado = {}
    for fid in factura_ids:
        resultado[fid] = float(por_recibos.get(fid, 0)) + float(por_anticipos.get(fid, 0))
    return resultado


def total(
    db: Session,
    cliente_id: int | None = None,
    estado: str | None = None,
    desde=None,
    hasta=None,
) -> float:
    """Suma de importes — se calcula SIEMPRE con SQL, nunca en el navegador.

    Las anuladas no suman. Si igual se pide el filtro estado='anulada',
    ahí sí se suman (es lo que se está pidiendo ver).
    """
    condiciones = _condiciones(cliente_id, estado, desde, hasta)
    if not estado:
        condiciones.append(Factura.estado != "anulada")
    valor = (
        db.query(func.sum(Factura.importe))
        .filter(*condiciones)
        .scalar()
    )
    return float(valor or 0)


def obtener(db: Session, factura_id: int) -> Factura:
    factura = db.get(Factura, factura_id)
    if factura is None:
        raise Rechazo("No existe esa factura", 404)
    return _con_asiento(db, factura)


# ================================================== IVA: lo desglosa el backend
# El contador carga el TOTAL y la alícuota; acá sale el neto y el IVA.
# Nunca en el navegador: si el cálculo viviera en el front, cada pantalla
# haría la cuenta un poco distinto y los libros no cerrarían con la pantalla.


def _desglosar_iva(
    db: Session, importe: float, alicuota_iva_id: int | None
) -> tuple[Decimal, Decimal, Decimal | None]:
    """(neto, iva, alícuota_aplicada) a partir del total facturado.

    La cuenta va al revés de lo que parece: si el total es 121,00 con 21%, el
    neto son 100,00 y el IVA 21,00. Por eso se divide primero por (1 + alícuota).

    Sin alícuota (monotributo, operaciones exentas): todo el importe es neto y
    el IVA va en cero.
    """
    total = Decimal(str(importe)).quantize(_DOS, rounding=ROUND_HALF_UP)

    if alicuota_iva_id is None:
        return total, Decimal("0.00"), None

    alicuota = db.get(AlicuotaIva, alicuota_iva_id)
    if alicuota is None:
        raise Rechazo(f"No existe la alícuota de IVA {alicuota_iva_id}", 400)
    if not alicuota.activo:
        raise Rechazo(
            f"La alícuota «{alicuota.nombre}» está dada de baja", 400
        )

    porcentaje = Decimal(str(alicuota.porcentaje))
    # neto = total / (1 + al/100). Se redondea el neto a 2 decimales y el IVA
    # sale por diferencia, así la suma da EXACTAMENTE el total que se facturó
    # (ni un centavo de más ni de menos).
    neto = (total / (Decimal("1") + porcentaje / Decimal("100"))).quantize(
        _DOS, rounding=ROUND_HALF_UP
    )
    iva = total - neto
    return neto, iva, porcentaje


def _verificar_relacion(db: Session, datos) -> None:
    """Chequea la factura a la que corrige una nota de crédito o de débito.

    Son tres cosas y todas importan:
      1. La factura tiene que existir.
      2. Tiene que ser del **mismo cliente**. Una nota de crédito contra el
         cliente equivocado descuenta deuda de quien no debe nada.
      3. Tiene que ser de otro tipo del que sea: no se puede "notar" una nota.
    """
    id_rel = getattr(datos, "factura_relacionada_id", None)
    if id_rel is None:
        return

    relacionada = db.get(Factura, int(id_rel))
    if relacionada is None:
        raise Rechazo("La factura que se quiere corregir no existe", 400)

    if relacionada.cliente_id != datos.cliente_id:
        raise Rechazo(
            "La nota tiene que ser del mismo cliente que la factura que corrige. "
            f"La factura {relacionada.punto_venta}-{relacionada.numero} es de "
            "otro cliente.",
            400,
        )

    if relacionada.tipo_comprobante not in ("factura_a", "factura_b", "factura_c"):
        raise Rechazo(
            "Una nota solo puede corregir a una FACTURA, no a otra nota. "
            f"La {relacionada.punto_venta}-{relacionada.numero} es "
            f"{ETIQUETAS_TIPO[relacionada.tipo_comprobante]}.",
            400,
        )

    if relacionada.estado == "anulada":
        raise Rechazo(
            "La factura que se quiere corregir está anulada: no tiene sentido "
            "notarla.",
            400,
        )


def _avisos_de_la_nota(db: Session, datos) -> list[str]:
    """Cosas que el contador tiene que saber pero que **no** bloquean la carga.

    Hoy hay una: si la factura que se corrige ya está pagada, la nota le
    devuelve plata al cliente y el saldo queda en contra. Puede ser legítimo
    (pagó de más y después se descuenta), así que se avisa en vez de cortar.
    """
    avisos = []
    id_rel = getattr(datos, "factura_relacionada_id", None)
    if id_rel is None:
        return avisos

    relacionada = db.get(Factura, int(id_rel))
    if relacionada is None:
        return avisos

    # `aplicado` NO se usa: es un campo calculado (la suma de los recibos), no
    # una columna de `facturas`, así que acá no existe y el acceso revienta con
    # AttributeError. Se usa el estado, que el backend ya recalcula al aplicar
    # un recibo.
    if relacionada.estado == "pagada":
        avisos.append(
            f"La factura {relacionada.punto_venta}-{relacionada.numero} ya está "
            "pagada. Esta nota le devuelve plata al cliente: el saldo va a "
            "quedar en contra y hay que devolvérsela por otro lado."
        )
    return avisos


def _verificar_unico(db: Session, datos, excluye: int | None = None) -> None:
    consulta = db.query(Factura).filter(
        Factura.tipo_comprobante == datos.tipo_comprobante,
        Factura.punto_venta == datos.punto_venta,
        Factura.numero == datos.numero,
    )
    if excluye:
        consulta = consulta.filter(Factura.id != excluye)
    if consulta.first():
        raise Rechazo(
            f"Ya existe {ETIQUETAS_TIPO[datos.tipo_comprobante]} "
            f"{datos.punto_venta}-{datos.numero}",
            409,
        )


def _desglosar_en_factura(db: Session, factura: Factura, datos) -> None:
    """Le completa a la factura el neto, el IVA y la alícuota aplicada."""
    neto, iva, aplicada = _desglosar_iva(
        db, float(datos.importe), datos.alicuota_iva_id
    )
    factura.tipo_operacion = datos.tipo_operacion
    factura.alicuota_iva_id = datos.alicuota_iva_id
    factura.alicuota_iva_aplicada = aplicada
    factura.neto = neto
    factura.iva = iva


def _verificar_periodo(db: Session, fecha, que: str) -> None:
    """Frena si la fecha cae en un período contable cerrado.

    Va en un `_` para que quede claro que es una guarda, no una función de
    negocio: en facturas, recibos y compras se llama en el MISMO lugar (primera
    línea de cada escritura) y tiene que decir lo mismo siempre.
    """
    from app.services import periodo_service

    periodo_service.verificar_abierto(db, fecha, que)


def crear(db: Session, datos: FacturaCrear) -> Factura:
    # Antes de validar nada: si el período de esa fecha está cerrado, no entra.
    # Es la primera comprobación para que el mensaje sea sobre el período y no
    # sobre un error técnico de los que vienen después.
    _verificar_periodo(db, datos.fecha, "cargar una factura con esa fecha")
    _verificar_unico(db, datos)
    _verificar_relacion(db, datos)
    campos = datos.model_dump()
    # El neto y el IVA no se copian del body: los calcula `_desglosar_iva`.
    for campo in ("neto", "iva", "alicuota_iva_aplicada"):
        campos.pop(campo, None)

    factura = Factura(**campos)
    _desglosar_en_factura(db, factura, datos)
    db.add(factura)
    db.commit()
    db.refresh(factura)

    # Una NC vinculada queda "compensada" apenas se emite (ver `recalcular_estado`),
    # y la factura de la que se descuenta tiene que ver el saldo bajar enseguida.
    recalcular_estado(db, factura.id)
    if factura.factura_relacionada_id:
        recalcular_estado(db, factura.factura_relacionada_id)
    db.refresh(factura)

    # El asiento sale acá, no con un botón aparte: una factura emitida es un
    # hecho, no un borrador. Si algo falla (falta configuración), la factura
    # queda igual — es preferible facturar sin asentar que no facturar.
    try:
        from app.services import asiento_automatico

        asiento_automatico.asiento_de_venta(db, factura.id)
    except Rechazo:
        pass
    db.refresh(factura)
    _con_asiento(db, factura)
    factura.avisos = _avisos_de_la_nota(db, datos)
    return factura


def actualizar(db: Session, factura_id: int, datos: FacturaActualizar) -> Factura:
    """Modificar la factura NO toca el asiento.

    El asiento ya contabilizado es un documento contable: si se modificara
    solo, el contador no podría tener la factura a la vista y el asiento
    distinto al mismo tiempo. Para tocarlo están los botones Generar /
    Modificar / Anular, que están del lado del asiento.
    """
    factura = obtener(db, factura_id)
    _verificar_periodo(db, factura.fecha, "modificar esa factura")
    _verificar_unico(db, datos, excluye=factura_id)
    for campo, valor in datos.model_dump().items():
        setattr(factura, campo, valor)
    _desglosar_en_factura(db, factura, datos)
    factura.actualizado = datetime.utcnow()
    db.commit()
    db.refresh(factura)
    recalcular_estado(db, factura_id)
    _con_asiento(db, factura)
    return factura


def _imputado(db: Session, factura_id: int) -> float:
    """Lo que ya se pagó por recibos Y por anticipos."""
    por_recibos = float(
        db.query(func.coalesce(func.sum(Aplicacion.importe), 0))
        .filter(Aplicacion.factura_id == factura_id)
        .scalar()
    )
    por_anticipos = float(
        db.query(func.coalesce(func.sum(AplicacionAnticipo.importe), 0))
        .filter(AplicacionAnticipo.factura_id == factura_id)
        .scalar()
    )
    return por_recibos + por_anticipos


def _creditos(db: Session, factura_id: int) -> float:
    """Las notas de crédito VINCULADAS a esta factura: lo que el cliente ya no
    tiene que pagar de ella.

    Una NC es una devolución a favor del cliente: cuando se emite, el Haber cae
    en la misma cuenta `1.1.03.02 Documentos a cobrar` que la factura. Por eso
    no hace falta que ningún recibo la "pague": ya está restada. Lo que hay que
    evitar es que quede colgada como si fuera algo impago, y por eso las NC
    vinculadas salen como "Compensada" (ver `recalcular_estado`).

    Se ignoran las NC anuladas: una nota anulada no resta nada.
    """
    return float(
        db.query(func.coalesce(func.sum(Factura.importe), 0))
        .filter(
            Factura.factura_relacionada_id == factura_id,
            Factura.tipo_comprobante.in_(TIPOS_NOTA_CREDITO),
            Factura.estado != "anulada",
        )
        .scalar()
    )


def saldo_pendiente(db: Session, factura_id: int) -> float:
    """Cuánto falta pagar de esta factura hoy: importe − créditos − cobrado.

    Es el mismo número con el que `recalcular_estado` decide si está pagada, y
    con el que la pantalla del recibo reparte el importe entre las facturas. Al
    estar en un solo lugar, lo que ve el contador y lo que se guarda no pueden
    diferir.
    """
    factura = db.get(Factura, factura_id)
    if factura is None:
        raise Rechazo("No existe esa factura", 404)
    if factura.tipo_comprobante in TIPOS_NOTA_CREDITO:
        # Una NC es un crédito: no tiene nada que cobrar.
        return 0.0
    return (
        float(factura.importe) - _creditos(db, factura_id) - _imputado(db, factura_id)
    )


def recalcular_estado(db: Session, factura_id: int) -> str:
    """El estado lo decide la suma de lo imputado — SUM en SQL, siempre.

    El saldo real de una factura es:

        importe − notas de crédito vinculadas − lo cobrado

    O sea que una factura de 1.000 con una NC de 300 tiene saldo 700, y queda
    "Pagada" en cuanto entran 700. Sin esto el contador veía una factura con
    300 pendientes que en realidad ya no le debía nadie.
    """
    factura = obtener(db, factura_id)
    if factura.estado == "anulada":
        return "anulada"

    # Una NC es un CRÉDITO, no una deuda: no tiene nada que cobrar. Si está
    # vinculada a una factura ya está compensada (el Haber de la NC y el Debe de
    # la factura están en la misma cuenta del cliente). Si NO está vinculada, es
    # un crédito a favor del cliente disponible para usar más adelante, y queda
    # "pendiente" a propósito.
    if factura.tipo_comprobante in TIPOS_NOTA_CREDITO:
        estado = "pagada" if factura.factura_relacionada_id else "pendiente"
    else:
        aplicado = _imputado(db, factura_id)
        saldo = float(factura.importe) - _creditos(db, factura_id) - aplicado
        if saldo <= _E:
            estado = "pagada"
        elif aplicado <= 0:
            estado = "pendiente"
        else:
            estado = "parcial"

    if factura.estado != estado:
        factura.estado = estado
        factura.actualizado = datetime.utcnow()
        db.commit()
        db.refresh(factura)
    return estado


def _tiene_aplicaciones(db: Session, factura_id: int) -> bool:
    """¿Ya hay recibos o anticipos imputados a esta factura?"""
    inspector = inspect(db.get_bind())
    for tabla in TABLAS_APLICACIONES:
        if not inspector.has_table(tabla):
            continue
        cantidad = db.execute(
            text(f"SELECT COUNT(*) FROM {tabla} WHERE factura_id = :id"),
            {"id": factura_id},
        ).scalar()
        if cantidad:
            return True
    return False


def eliminar(db: Session, factura_id: int) -> None:
    factura = obtener(db, factura_id)
    if _tiene_aplicaciones(db, factura_id):
        raise Rechazo(
            "No se puede eliminar: la factura tiene cobros imputados "
            "(recibos o anticipos). Sacá esas imputaciones o anulá la factura.",
            409,
        )
    # Una factura tiene asiento siempre (se genera al darla de alta). El
    # asiento es un documento contable y NO se borra junto con la factura: se
    # anula desde el botón "Anular asiento". Si se lo borrara, el número del
    # comprobante quedaría libre y el siguiente reusaría un número ya usado.
    if factura.id_asiento is not None:
        raise Rechazo(
            f"La factura tiene el asiento {factura.numero_comprobante_asiento}, "
            "que ya está contabilizado. Un asiento no se borra: anulalo desde "
            "la factura y después anotá la factura.",
            409,
        )
    db.delete(factura)
    db.commit()


def _marcar(db: Session, factura: Factura, estado: str) -> Factura:
    factura.estado = estado
    factura.actualizado = datetime.utcnow()
    db.commit()
    db.refresh(factura)
    return factura


def anular(db: Session, factura_id: int) -> Factura:
    """Solo admin (el rol se controla en el router).

    OJO: anular la factura **no anula el asiento**. Son dos cosas distintas y
    el contador decide el orden: puede anular una factura y dejar el asiento
    dando por lo que se quiso dar en libros. Para tocar el asiento está el
    botón "Anular asiento".

    Si la que se anula es una NC, la factura de la que estaba vinculada vuelve a
    deber lo que la nota le cubría: el crédito dejó de existir.
    """
    factura = obtener(db, factura_id)
    _verificar_periodo(db, factura.fecha, "anular esa factura")
    relacionada = factura.factura_relacionada_id
    anulada = _marcar(db, factura, "anulada")
    if relacionada:
        recalcular_estado(db, relacionada)
    return anulada


def reabrir(db: Session, factura_id: int) -> Factura:
    """Vuelve a 'pendiente'. Si ya hay recibos, el estado se recalcula
    recién cuando se aplican o desaplican pagos."""
    factura = obtener(db, factura_id)
    _verificar_periodo(db, factura.fecha, "reabrir esa factura")
    relacionada = factura.factura_relacionada_id
    reabierta = _marcar(db, factura, "pendiente")
    # Al reabrir una NC vuelve a compensar: hay que recalcular la propia (por
    # si es NC, "pagada"/"pendiente") y la factura de la que depende.
    recalcular_estado(db, factura_id)
    if relacionada:
        recalcular_estado(db, relacionada)
    db.refresh(reabierta)
    return reabierta


# --------------------------------------------------------------------- Excel

def informe_excel(facturas: list[Factura], total_facturado: float) -> bytes:
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Facturas"

    columnas = [
        ("Fecha", 12),
        ("Tipo", 20),
        ("Punto de venta", 15),
        ("Número", 12),
        ("Cliente", 30),
        ("Concepto", 40),
        ("Importe", 14),
        ("Vencimiento", 14),
        ("Condición", 22),
        ("Estado", 20),
        ("CAE", 22),
        ("Vto. CAE", 12),
    ]
    hoja.append([settings.nombre_estudio])
    hoja.cell(row=1, column=1).font = Font(bold=True, size=13)
    hoja.append([])

    hoja.append([nombre for nombre, _ in columnas])
    for celda in hoja[3]:
        celda.font = Font(bold=True)

    for f in facturas:
        hoja.append(
            [
                f.fecha.isoformat(),
                ETIQUETAS_TIPO[f.tipo_comprobante],
                f.punto_venta,
                f.numero,
                f.cliente_nombre,
                f.concepto or "",
                float(f.importe),
                f.fecha_vencimiento.isoformat() if f.fecha_vencimiento else "",
                ETIQUETAS_CONDICION[f.condicion_venta],
                ETIQUETAS_ESTADO[f.estado],
                f.cae or "",
                f.cae_vencimiento.isoformat() if f.cae_vencimiento else "",
            ]
        )

    hoja.append([""] * len(columnas))
    hoja.append(["", "", "", "", "", "TOTAL", total_facturado])
    ultima = hoja.max_row
    hoja.cell(row=ultima, column=6).font = Font(bold=True)
    celda_total = hoja.cell(row=ultima, column=7)
    celda_total.font = Font(bold=True)
    celda_total.number_format = "#,##0.00"

    for (nombre, ancho), letra in zip(columnas, "ABCDEFGHIJKL"):
        hoja.column_dimensions[letra].width = ancho

    salida = BytesIO()
    libro.save(salida)
    return salida.getvalue()


# ---------------------------------------------------------------------- PDF

_ANCHO = 18 * cm  # A4 con margen de 1,5 cm a cada lado


def _caja(pares: list[tuple[str, str]]) -> Table:
    """Recuadro etiqueta + valor. Los valores van en Paragraph para que
    se corten en varias líneas si son largos (un domicilio largo, p. ej.).
    """
    rotulo = ParagraphStyle(
        "rotulo", fontName="Helvetica-Bold", fontSize=9, leading=11,
        textColor=colors.HexColor("#4a5163"),
    )
    valor = ParagraphStyle("valor", fontName="Helvetica", fontSize=9, leading=11)

    filas = [
        [Paragraph(escape(k), rotulo), Paragraph(escape(v or "—"), valor)]
        for k, v in pares
    ]
    tabla = Table(filas, colWidths=[4.2 * cm, _ANCHO - 4.2 * cm])
    tabla.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef1f7")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c9ced9")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return tabla


def pdf(db: Session, factura_id: int) -> bytes:
    """El comprobante en PDF — es lo que se le adjunta al cliente por mail."""
    factura = obtener(db, factura_id)
    cliente = factura.cliente
    tipo = ETIQUETAS_TIPO[factura.tipo_comprobante]

    identificacion = " · ".join(
        x
        for x in (
            f"CUIT {cliente.cuit}" if cliente and cliente.cuit else "",
            f"DNI {cliente.dni}" if cliente and cliente.dni else "",
        )
        if x
    )
    localidad = " · ".join(
        x
        for x in (
            cliente.localidad if cliente else "",
            f"({cliente.codigo_postal})" if cliente and cliente.codigo_postal else "",
            cliente.provincia if cliente else "",
        )
        if x
    )

    buffer = BytesIO()
    documento = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=f"{tipo} {factura.punto_venta}-{factura.numero}",
    )

    estilos = getSampleStyleSheet()
    historias = [
        Paragraph(settings.nombre_estudio, estilos["Title"]),
        Paragraph(tipo, estilos["Heading2"]),
        Paragraph(
            f"Punto de venta {factura.punto_venta} · N° {factura.numero}",
            estilos["Normal"],
        ),
        Spacer(1, 8 * mm),
        _caja(
            [
                ("Cliente", cliente.nombre_completo if cliente else ""),
                ("CUIT / DNI", identificacion),
                ("Domicilio", cliente.domicilio if cliente else ""),
                ("Localidad", localidad),
                ("Email", cliente.email if cliente else ""),
            ]
        ),
        Spacer(1, 6 * mm),
        _caja(
            [
                ("Fecha", factura.fecha.strftime("%d/%m/%Y")),
                (
                    "Vencimiento",
                    factura.fecha_vencimiento.strftime("%d/%m/%Y")
                    if factura.fecha_vencimiento
                    else "",
                ),
                ("Condición", ETIQUETAS_CONDICION[factura.condicion_venta]),
                ("Estado", ETIQUETAS_ESTADO[factura.estado]),
            ]
        ),
    ]

    if factura.concepto:
        historias += [
            Spacer(1, 6 * mm),
            Paragraph(
                f"<b>Concepto:</b> {escape(factura.concepto)}", estilos["Normal"]
            ),
        ]

    # el importe va grande y a la derecha, con una línea arriba
    historias.append(Spacer(1, 8 * mm))
    importe = Table(
        [["IMPORTE", f"$ {pesos(float(factura.importe))}"]],
        colWidths=[12.0 * cm, 6.0 * cm],
    )
    importe.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (0, 0), 9),
                ("FONTSIZE", (1, 0), (1, 0), 16),
                ("TEXTCOLOR", (0, 0), (0, 0), colors.HexColor("#4a5163")),
                ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                ("LINEABOVE", (0, 0), (-1, 0), 1, colors.HexColor("#070b14")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    historias.append(importe)

    if factura.cae:
        historias += [
            Spacer(1, 10 * mm),
            Paragraph(
                "CAE "
                + escape(factura.cae)
                + (
                    f" · Vencimiento {factura.cae_vencimiento.strftime('%d/%m/%Y')}"
                    if factura.cae_vencimiento
                    else ""
                ),
                estilos["Normal"],
            ),
        ]

    documento.build(historias)
    return buffer.getvalue()
