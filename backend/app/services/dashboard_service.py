from datetime import date, datetime, timedelta
from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session

from app.models.cliente import Cliente
from app.models.factura import Factura, ESTADOS as FACTURA_ESTADOS
from app.models.recibo import Recibo
from app.models.anticipo import Anticipo
from app.core.errors import Rechazo


def _inicio_mes(d: date = None) -> date:
    """Primer día del mes actual."""
    d = d or date.today()
    return d.replace(day=1)


def _fin_mes(d: date = None) -> date:
    """Último día del mes actual."""
    d = d or date.today()
    if d.month == 12:
        return d.replace(day=31)
    return (d.replace(month=d.month + 1, day=1)) - timedelta(days=1)


def kpis(db: Session) -> dict:
    """KPIs del dashboard."""
    hoy = date.today()
    ini_mes = _inicio_mes(hoy)
    fin_mes = _fin_mes(hoy)

    # Clientes activos (con al menos una factura o recibo)
    clientes_activos = db.query(func.count(func.distinct(Cliente.id))).join(
        Factura, Factura.cliente_id == Cliente.id, isouter=True
    ).join(
        Recibo, Recibo.cliente_id == Cliente.id, isouter=True
    ).filter(
        or_(Factura.id.isnot(None), Recibo.id.isnot(None))
    ).scalar() or 0

    # Facturado este mes (solo facturas no anuladas)
    facturado_mes = db.query(func.coalesce(func.sum(Factura.importe), 0)).filter(
        Factura.fecha >= ini_mes,
        Factura.fecha <= fin_mes,
        Factura.estado != "anulada"
    ).scalar() or 0

    # Cobrado este mes (recibos emitidos)
    cobrado_mes = db.query(func.coalesce(func.sum(Recibo.importe), 0)).filter(
        Recibo.fecha >= ini_mes,
        Recibo.fecha <= fin_mes
    ).scalar() or 0

    # Pendiente (facturado - cobrado del mes) - pero mejor calcular como saldo total pendiente
    # Para el dashboard: facturado mes - cobrado mes
    pendiente_mes = float(facturado_mes) - float(cobrado_mes)

    # Facturas vencidas (estado pendiente/parcial y fecha_vencimiento < hoy)
    facturas_vencidas = db.query(func.count(Factura.id)).filter(
        Factura.estado.in_(["pendiente", "parcial"]),
        Factura.fecha_vencimiento < hoy,
        Factura.fecha_vencimiento.isnot(None)
    ).scalar() or 0

    return {
        "clientes_activos": int(clientes_activos),
        "facturado_mes": float(facturado_mes),
        "cobrado_mes": float(cobrado_mes),
        "pendiente_mes": float(pendiente_mes),
        "facturas_vencidas": int(facturas_vencidas),
    }


def alertas_vencimiento(db: Session, limite_dias: int = 30) -> list:
    """Alertas de vencimiento de facturas."""
    hoy = date.today()
    limite = hoy + timedelta(days=limite_dias)

    facturas = db.query(Factura).filter(
        Factura.estado.in_(["pendiente", "parcial"]),
        Factura.fecha_vencimiento.isnot(None),
        Factura.fecha_vencimiento <= limite
    ).order_by(Factura.fecha_vencimiento.asc()).all()

    alertas = []
    for f in facturas:
        dias = (f.fecha_vencimiento - hoy).days
        if dias < 0:
            nivel = "rojo"      # vencida
            label = f"Vencida hace {abs(dias)} día{'s' if abs(dias) > 1 else ''}"
        elif dias <= 3:
            nivel = "naranja"   # vence en 3 días
            label = f"Vence en {dias} día{'s' if dias > 1 else ''}"
        else:
            nivel = "amarillo"  # vence pronto
            label = f"Vence en {dias} día{'s' if dias > 1 else ''}"

        alertas.append({
            "factura_id": f.id,
            "tipo_comprobante": f.tipo_comprobante,
            "punto_venta": f.punto_venta,
            "numero": f.numero,
            "cliente_nombre": f.cliente.nombre_completo if f.cliente else "",
            "fecha_vencimiento": f.fecha_vencimiento.isoformat(),
            "importe": float(f.importe),
            "dias": dias,
            "nivel": nivel,
            "label": label,
        })

    return alertas


def facturas_por_vencer(db: Session, dias: int = 7) -> list:
    """Facturas que vencen en los próximos N días (para tabla)."""
    hoy = date.today()
    limite = hoy + timedelta(days=dias)

    facturas = db.query(Factura).filter(
        Factura.estado.in_(["pendiente", "parcial"]),
        Factura.fecha_vencimiento.isnot(None),
        Factura.fecha_vencimiento >= date.today(),
        Factura.fecha_vencimiento <= date.today() + timedelta(days=dias)
    ).order_by(Factura.fecha_vencimiento.asc()).all()

    return [
        {
            "id": f.id,
            "tipo_comprobante": f.tipo_comprobante,
            "punto_venta": f.punto_venta,
            "numero": f.numero,
            "cliente_nombre": f.cliente.nombre_completo if f.cliente else "",
            "fecha_vencimiento": f.fecha_vencimiento.isoformat(),
            "importe": float(f.importe),
            "dias_restantes": (f.fecha_vencimiento - date.today()).days,
        }
        for f in facturas
    ]