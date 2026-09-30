from sqlalchemy import Integer, Numeric, String, func, literal, select, union_all
from sqlalchemy.orm import Session

from app.models.anticipo import Anticipo
from app.models.factura import Factura
from app.models.recibo import Recibo
from app.schemas.factura import ETIQUETAS_TIPO
from app.schemas.recibo import CuentaCorrienteOut, MovimientoOut
from app.services import cliente_service

CERO = literal(0, Numeric(14, 2))
# orden de los movimientos de un mismo día: primero lo que se DEBE,
# después lo que se pagó (HABER) y al final las anulaciones.
DEBE_PRIMERO = literal(0, Integer)
HABER_DESPUES = literal(1, Integer)
ANULACION = literal(2, Integer)


def _movimientos(db: Session, cliente_id: int):
    """Facturas (DEBE) + recibos y anticipos (HABER) del cliente, en una tabla."""
    facturas = (
        select(
            Factura.fecha.label("fecha"),
            literal("factura", String(10)).label("origen"),
            DEBE_PRIMERO.label("orden"),
            Factura.id.label("ref_id"),
            Factura.tipo_comprobante.label("tipo"),
            func.concat(Factura.punto_venta, "-", Factura.numero).label("numero"),
            Factura.importe.label("debe"),
            CERO.label("haber"),
        ).where(Factura.cliente_id == cliente_id, Factura.estado != "anulada")
    )
    recibos = select(
        Recibo.fecha,
        literal("recibo", String(10)),
        HABER_DESPUES,
        Recibo.id,
        literal("", String(10)),
        Recibo.numero,
        CERO,
        Recibo.importe,
    ).where(Recibo.cliente_id == cliente_id)
    anticipos = select(
        Anticipo.fecha,
        literal("anticipo", String(10)),
        HABER_DESPUES,
        Anticipo.id,
        literal("", String(10)),
        Anticipo.numero,
        CERO,
        Anticipo.importe,
    ).where(Anticipo.cliente_id == cliente_id)
    # Un anticipo eliminado genera su movimiento contrario en DEBE, para que
    # el estado de cuenta muestre qué pasó (la plata se devolvió).
    anticipos_eliminados = select(
        Anticipo.fecha,
        literal("anticipo_eliminado", String(24)),
        ANULACION,
        Anticipo.id,
        literal("", String(10)),
        Anticipo.numero,
        Anticipo.importe,
        CERO,
    ).where(
        Anticipo.cliente_id == cliente_id,
        Anticipo.estado == "eliminado",
    )
    return union_all(
        facturas, recibos, anticipos, anticipos_eliminados
    ).subquery("mov")


def movimientos(db: Session, cliente_id: int) -> CuentaCorrienteOut:
    """Historial con saldo corrido y totales — todo calculado con SQL.

    Imputar un anticipo NO agrega un movimiento nuevo: la plata ya entró
    como HABER al alta, la imputación solo marca a qué factura va.
    """
    cliente = cliente_service.obtener(db, cliente_id)
    m = _movimientos(db, cliente_id)

    consulta = select(
        m.c.fecha,
        m.c.origen,
        m.c.tipo,
        m.c.numero,
        m.c.debe,
        m.c.haber,
        # saldo corrido: SUM(DEBE − HABER) hasta esa fila, en la base de datos
        func.sum(m.c.debe - m.c.haber)
        .over(order_by=[m.c.fecha, m.c.orden, m.c.ref_id])
        .label("saldo"),
    ).order_by(m.c.fecha, m.c.orden, m.c.ref_id)

    filas = []
    for fila in db.execute(consulta):
        if fila.origen == "factura":
            concepto = f"{ETIQUETAS_TIPO.get(fila.tipo, fila.tipo)} {fila.numero}"
        elif fila.origen == "anticipo_eliminado":
            concepto = f"Eliminación anticipos {fila.numero}"
        elif fila.origen == "anticipo":
            concepto = f"Anticipo {fila.numero}"
        else:
            concepto = f"Recibo {fila.numero}"
        filas.append(
            MovimientoOut(
                fecha=fila.fecha,
                concepto=concepto,
                debe=float(fila.debe or 0),
                haber=float(fila.haber or 0),
                saldo=float(fila.saldo or 0),
            )
        )

    total_debe, total_haber = db.execute(
        select(
            func.coalesce(func.sum(m.c.debe), 0),
            func.coalesce(func.sum(m.c.haber), 0),
        )
    ).one()

    debe = float(total_debe)
    haber = float(total_haber)
    return CuentaCorrienteOut(
        cliente_id=cliente.id,
        cliente_nombre=cliente.nombre_completo,
        movimientos=filas,
        total_debe=debe,
        total_haber=haber,
        saldo=debe - haber,
    )
