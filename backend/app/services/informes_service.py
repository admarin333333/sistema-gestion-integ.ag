from datetime import date, datetime, timedelta
from sqlalchemy import func, or_, and_, case
from sqlalchemy.orm import Session

from app.models.factura import Factura, ESTADOS as FACTURA_ESTADOS, TIPOS_COMPROBANTE
from app.models.anticipo import Anticipo, ESTADOS_ANTICIPO
from app.models.recibo import Recibo
from app.models.cliente import Cliente
from app.config import settings
from app.core.errors import Rechazo


# Etiquetas para tipos de comprobante
ETIQUETAS_TIPO = {
    "factura_a": "Factura A",
    "factura_b": "Factura B",
    "factura_c": "Factura C",
    "nota_credito_a": "Nota de Crédito A",
    "nota_credito_b": "Nota de Crédito B",
    "nota_credito_c": "Nota de Crédito C",
    "nota_debito_a": "Nota de Débito A",
    "nota_debito_b": "Nota de Débito B",
    "nota_debito_c": "Nota de Débito C",
}

ETIQUETAS_ESTADO_FACTURA = {
    "pendiente": "Pendiente",
    "parcial": "Parcialmente pagada",
    "pagada": "Pagada",
    "anulada": "Anulada",
}

ETIQUETAS_ESTADO_ANTICIPO = {
    "disponible": "Disponible",
    "parcial": "Parcial",
    "aplicado": "Aplicado",
    "eliminado": "Eliminado",
}


def _condiciones_fecha(desde, hasta):
    """Condiciones de fecha reutilizables."""
    condiciones = []
    if desde:
        condiciones.append({"desde": desde})
    if hasta:
        condiciones.append({"hasta": hasta})
    return condiciones


def _filtrar_fecha(query, campo_fecha, desde, hasta):
    """Aplica filtros de fecha a una query."""
    if desde:
        query = query.filter(campo_fecha >= desde)
    if hasta:
        query = query.filter(campo_fecha <= hasta)
    return query


def informe_estado_deuda(
    db: Session,
    desde: date = None,
    hasta: date = None,
    cliente_id: int = None,
) -> dict:
    """
    Informe de Estado de Deuda Total.
    Incluye: Facturas, Notas de Crédito, Notas de Débito pendientes de pago.
    Filtros: desde, hasta, cliente_id.
    """
    # Estados que se consideran "pendientes de pago"
    estados_pendientes = ["pendiente", "parcial"]
    
    # Base query para facturas pendientes
    query = db.query(Factura).join(Cliente).filter(
        Factura.estado.in_(estados_pendientes)
    )
    
    if desde:
        query = query.filter(Factura.fecha >= desde)
    if hasta:
        query = query.filter(Factura.fecha <= hasta)
    if cliente_id:
        query = query.filter(Factura.cliente_id == cliente_id)
    
    facturas = query.order_by(Factura.fecha.asc(), Factura.id.asc()).all()
    
    # Calcular totales por tipo de comprobante
    totales = {}
    for f in facturas:
        tipo_label = ETIQUETAS_TIPO.get(f.tipo_comprobante, f.tipo_comprobante)
        if tipo_label not in totales:
            totales[tipo_label] = {"cantidad": 0, "importe": 0.0, "pendiente": 0.0}
        totales[tipo_label]["cantidad"] += 1
        totales[tipo_label]["importe"] += float(f.importe)
        # Calcular pendiente (importe - lo pagado)
        pagado = float(f.importe) - float(f.importe) * (0 if f.estado == "pendiente" else 0.5 if f.estado == "parcial" else 1)
        # Mejor calcular desde aplicaciones
        pendiente = float(f.importe) - pagado
        totales[tipo_label]["pendiente"] += pendiente
    
    # Calcular pendiente real desde aplicaciones de recibo y anticipo
    from app.models.recibo import Aplicacion
    from app.models.anticipo import AplicacionAnticipo
    from sqlalchemy import func
    
    facturas_dict = {f.id: f for f in facturas}
    if facturas_dict:
        # Recibos aplicados
        recibos_aplicados = dict(
            db.query(Aplicacion.factura_id, func.coalesce(func.sum(Aplicacion.importe), 0))
            .filter(Aplicacion.factura_id.in_(facturas_dict.keys()))
            .group_by(Aplicacion.factura_id)
            .all()
        )
        # Anticipos aplicados
        anticipos_aplicados = dict(
            db.query(AplicacionAnticipo.factura_id, func.coalesce(func.sum(AplicacionAnticipo.importe), 0))
            .filter(AplicacionAnticipo.factura_id.in_(facturas_dict.keys()))
            .group_by(AplicacionAnticipo.factura_id)
            .all()
        )
        
        for f in facturas:
            pagado = float(recibos_aplicados.get(f.id, 0)) + float(anticipos_aplicados.get(f.id, 0))
            pendiente = float(f.importe) - pagado
            if pendiente < 0.005:
                pendiente = 0
            f.pendiente_calculado = pendiente
    
    # Agrupar por tipo para totales
    resumen = {}
    for f in facturas:
        tipo = ETIQUETAS_TIPO.get(f.tipo_comprobante, f.tipo_comprobante)
        if tipo not in resumen:
            resumen[tipo] = {"cantidad": 0, "total": 0.0, "pendiente": 0.0}
        resumen[tipo]["cantidad"] += 1
        resumen[tipo]["total"] += float(f.importe)
        resumen[tipo]["pendiente"] += getattr(f, "pendiente_calculado", 0)
    
    # Totales generales
    total_general = sum(r["total"] for r in resumen.values())
    pendiente_general = sum(r["pendiente"] for r in resumen.values())
    
    # Preparar items para la tabla
    items = []
    for f in facturas:
        items.append({
            "fecha": f.fecha.isoformat(),
            "tipo": ETIQUETAS_TIPO.get(f.tipo_comprobante, f.tipo_comprobante),
            "punto_venta": f.punto_venta,
            "numero": f.numero,
            "cliente": f.cliente.nombre_completo if f.cliente else "",
            "concepto": f.concepto or "",
            "importe": float(f.importe),
            "pendiente": getattr(f, "pendiente_calculado", 0),
            "estado": ETIQUETAS_ESTADO_FACTURA.get(f.estado, f.estado),
            "fecha_vencimiento": f.fecha_vencimiento.isoformat() if f.fecha_vencimiento else None,
        })
    
    return {
        "desde": desde.isoformat() if desde else None,
        "hasta": hasta.isoformat() if hasta else None,
        "cliente_id": cliente_id,
        "items": items,
        "resumen": resumen,
        "total_general": total_general,
        "pendiente_general": pendiente_general,
        "cantidad_total": len(items),
    }


def informe_anticipos_pendientes(
    db: Session,
    desde: date = None,
    hasta: date = None,
    cliente_id: int = None,
) -> dict:
    """
    Listado de Anticipos Pendientes de Imputación.
    Estados: disponible, parcial (tienen saldo disponible).
    Filtros: desde, hasta, cliente_id.
    """
    estados_con_saldo = ["disponible", "parcial"]
    
    query = db.query(Anticipo).join(Cliente).filter(
        Anticipo.estado.in_(estados_con_saldo)
    )
    
    if desde:
        query = query.filter(Anticipo.fecha >= desde)
    if hasta:
        query = query.filter(Anticipo.fecha <= hasta)
    if cliente_id:
        query = query.filter(Anticipo.cliente_id == cliente_id)
    
    anticipos = query.order_by(Anticipo.fecha.asc(), Anticipo.id.asc()).all()
    
    from app.models.anticipo import AplicacionAnticipo
    from sqlalchemy import func
    
    # Calcular imputado y disponible para cada anticipo
    if anticipos:
        ids = [a.id for a in anticipos]
        imputados = dict(
            db.query(AplicacionAnticipo.anticipo_id, func.coalesce(func.sum(AplicacionAnticipo.importe), 0))
            .filter(AplicacionAnticipo.anticipo_id.in_(ids))
            .group_by(AplicacionAnticipo.anticipo_id)
            .all()
        )
    
    items = []
    total_importe = 0.0
    total_disponible = 0.0
    total_imputado = 0.0
    
    for a in anticipos:
        imputado = float(imputados.get(a.id, 0))
        disponible = float(a.importe) - imputado
        if disponible < 0.005:
            disponible = 0
        
        total_importe += float(a.importe)
        total_imputado += imputado
        total_disponible += disponible
        
        items.append({
            "fecha": a.fecha.isoformat(),
            "numero": a.numero,
            "cliente": a.cliente.nombre_completo if a.cliente else "",
            "importe": float(a.importe),
            "imputado": imputado,
            "disponible": disponible,
            "estado": ETIQUETAS_ESTADO_ANTICIPO.get(a.estado, a.estado),
        })
    
    resumen = {
        "total_importe": total_importe,
        "total_imputado": total_imputado,
        "total_disponible": total_disponible,
        "cantidad": len(items),
    }
    
    return {
        "desde": desde.isoformat() if desde else None,
        "hasta": hasta.isoformat() if hasta else None,
        "cliente_id": cliente_id,
        "items": items,
        "resumen": resumen,
    }


# --- Excel exports ---

def estado_deuda_excel(data: dict) -> bytes:
    """Genera Excel del informe de estado de deuda."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment
    from io import BytesIO
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Estado de Deuda"
    
    # Encabezado
    ws.append([settings.nombre_estudio])
    ws.cell(row=1, column=1).font = Font(bold=True, size=14)
    ws.append(["ESTADO DE DEUDA TOTAL"])
    ws.cell(row=2, column=1).font = Font(bold=True, size=12)
    
    if data["desde"] or data["hasta"]:
        rango = f"Desde: {data['desde'] or 'inicio'}  Hasta: {data['hasta'] or 'hoy'}"
        ws.append([rango])
    
    ws.append([])
    
    # Items
    headers = ["Fecha", "Tipo", "Punto Venta", "Número", "Cliente", "Concepto", "Importe", "Pendiente", "Estado", "Vencimiento"]
    ws.append(headers)
    for cell in ws[ws.max_row]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")
    
    for item in data["items"]:
        ws.append([
            item["fecha"],
            item["tipo"],
            item["punto_venta"],
            item["numero"],
            item["cliente"],
            item["concepto"],
            item["importe"],
            item["pendiente"],
            item["estado"],
            item["fecha_vencimiento"] or "",
        ])
    
    # Totales
    ws.append([])
    ws.append(["", "", "", "", "TOTALES", "", data["total_general"], data["pendiente_general"], "", ""])
    last_row = ws.max_row
    for col in range(1, len(data["items"][0]) + 1 if data["items"] else 10):
        cell = ws.cell(row=last_row, column=col)
        cell.font = Font(bold=True)
    
    # Ajustar anchos
    for col, width in enumerate([12, 20, 12, 12, 30, 35, 14, 14, 18, 12], 1):
        ws.column_dimensions[chr(64 + col)].width = width
    
    output = BytesIO()
    wb.save(output)
    return output.getvalue()


def anticipos_pendientes_excel(data: dict) -> bytes:
    """Genera Excel del informe de anticipos pendientes."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment
    from io import BytesIO
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Anticipos Pendientes"
    
    ws.append([settings.nombre_estudio])
    ws.cell(row=1, column=1).font = Font(bold=True, size=14)
    ws.append(["ANTICIPOS PENDIENTES DE IMPUTACIÓN"])
    ws.cell(row=2, column=1).font = Font(bold=True, size=12)
    
    if data["desde"] or data["hasta"]:
        ws.append([f"Desde: {data['desde'] or 'inicio'}  Hasta: {data['hasta'] or 'hoy'}"])
    
    ws.append([])
    
    headers = ["Fecha", "Número", "Cliente", "Importe", "Imputado", "Disponible", "Estado"]
    ws.append(headers)
    for cell in ws[ws.max_row]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")
    
    for item in data["items"]:
        ws.append([
            item["fecha"],
            item["numero"],
            item["cliente"],
            item["importe"],
            item["imputado"],
            item["disponible"],
            item["estado"],
        ])
    
    ws.append([])
    ws.append(["", "", "TOTALES", data["resumen"]["total_importe"], data["resumen"]["total_imputado"], data["resumen"]["total_disponible"], ""])
    last_row = ws.max_row
    for col in range(1, 8):
        cell = ws.cell(row=last_row, column=col)
        cell.font = Font(bold=True)
    
    for col, width in enumerate([12, 12, 30, 14, 14, 14, 15], 1):
        ws.column_dimensions[chr(64 + col)].width = width
    
    output = BytesIO()
    wb.save(output)
    return output.getvalue()