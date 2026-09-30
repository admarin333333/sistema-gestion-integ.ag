from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape

from openpyxl import Workbook
from openpyxl.styles import Font
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import func, inspect, text
from sqlalchemy.orm import Session

from app.core.errors import Rechazo
from app.models.anticipo import AplicacionAnticipo
from app.models.factura import ESTADOS, Factura
from app.models.recibo import Aplicacion
from app.schemas.factura import ETIQUETAS_CONDICION, ETIQUETAS_ESTADO, ETIQUETAS_TIPO
from app.schemas.factura import FacturaActualizar, FacturaCrear
from app.config import settings
from app.services.formato import pesos

# Tabla que se crea junto con los recibos (paso siguiente de la Fase 3).
# Tablas donde puede estar imputada una factura (recibos y anticipos).
TABLAS_APLICACIONES = ("aplicaciones_recibo", "aplicaciones_anticipo")


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
        return consulta.order_by(Factura.fecha.desc(), Factura.id.desc()).all()
    return consulta.order_by(Factura.fecha.asc(), Factura.id.asc()).all()


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
    return factura


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


def crear(db: Session, datos: FacturaCrear) -> Factura:
    _verificar_unico(db, datos)
    factura = Factura(**datos.model_dump())
    db.add(factura)
    db.commit()
    db.refresh(factura)
    return factura


def actualizar(db: Session, factura_id: int, datos: FacturaActualizar) -> Factura:
    factura = obtener(db, factura_id)
    _verificar_unico(db, datos, excluye=factura_id)
    for campo, valor in datos.model_dump().items():
        setattr(factura, campo, valor)
    factura.actualizado = datetime.utcnow()
    db.commit()
    db.refresh(factura)
    recalcular_estado(db, factura_id)
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


def recalcular_estado(db: Session, factura_id: int) -> str:
    """El estado lo decide la suma de lo imputado — SUM en SQL, siempre."""
    factura = obtener(db, factura_id)
    if factura.estado == "anulada":
        return "anulada"

    aplicado = _imputado(db, factura_id)
    importe = float(factura.importe)
    if aplicado <= 0:
        estado = "pendiente"
    elif aplicado < importe:
        estado = "parcial"
    else:
        estado = "pagada"

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
    db.delete(factura)
    db.commit()


def _marcar(db: Session, factura: Factura, estado: str) -> Factura:
    factura.estado = estado
    factura.actualizado = datetime.utcnow()
    db.commit()
    db.refresh(factura)
    return factura


def anular(db: Session, factura_id: int) -> Factura:
    """Solo admin (el rol se controla en el router)."""
    return _marcar(db, obtener(db, factura_id), "anulada")


def reabrir(db: Session, factura_id: int) -> Factura:
    """Vuelve a 'pendiente'. Si ya hay recibos, el estado se recalcula
    recién cuando se aplican o desaplican pagos."""
    return _marcar(db, obtener(db, factura_id), "pendiente")


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
