from datetime import datetime
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.errors import Rechazo
from app.models.anticipo import AplicacionAnticipo, Anticipo
from app.models.factura import Factura
from app.config import settings
from app.schemas.anticipo import (
    AplicacionAnticipoCrear,
    AnticipoActualizar,
    AnticipoCrear,
    ETIQUETAS_ESTADO,
)
from app.services import factura_service

# Tolerancia de centavos: los decimales flotantes no cierran exactos.
_E = 0.005


def _condiciones(cliente_id, desde, hasta) -> list:
    condiciones = []
    if cliente_id is not None:
        condiciones.append(Anticipo.cliente_id == cliente_id)
    if desde is not None:
        condiciones.append(Anticipo.fecha >= desde)
    if hasta is not None:
        condiciones.append(Anticipo.fecha <= hasta)
    return condiciones


def listar(
    db: Session,
    cliente_id: int | None = None,
    desde=None,
    hasta=None,
) -> list[Anticipo]:
    consulta = db.query(Anticipo).filter(*_condiciones(cliente_id, desde, hasta))
    return consulta.order_by(Anticipo.fecha.desc(), Anticipo.id.desc()).all()


def total(
    db: Session,
    cliente_id: int | None = None,
    desde=None,
    hasta=None,
) -> float:
    """Suma de importes — se calcula SIEMPRE con SQL, nunca en el navegador."""
    valor = (
        db.query(func.sum(Anticipo.importe))
        .filter(*_condiciones(cliente_id, desde, hasta))
        .scalar()
    )
    return float(valor or 0)


def obtener(db: Session, anticipo_id: int) -> Anticipo:
    anticipo = db.get(Anticipo, anticipo_id)
    if anticipo is None:
        raise Rechazo("No existe ese anticipo", 404)
    return anticipo


def _verificar_unico(db: Session, numero: str, excluye: int | None = None) -> None:
    consulta = db.query(Anticipo).filter(Anticipo.numero == numero)
    if excluye:
        consulta = consulta.filter(Anticipo.id != excluye)
    if consulta.first():
        raise Rechazo(f"Ya existe el anticipo {numero}", 409)


def crear(db: Session, datos: AnticipoCrear) -> Anticipo:
    _verificar_unico(db, datos.numero)
    anticipo = Anticipo(**datos.model_dump())
    db.add(anticipo)
    db.commit()
    db.refresh(anticipo)
    return anticipo


def actualizar(db: Session, anticipo_id: int, datos: AnticipoActualizar) -> Anticipo:
    anticipo = obtener(db, anticipo_id)
    if anticipo.estado == "eliminado":
        raise Rechazo("No se puede modificar un anticipo eliminado", 409)
    _verificar_unico(db, datos.numero, excluye=anticipo_id)
    aplicado = _suma(db, AplicacionAnticipo.anticipo_id == anticipo_id)
    if aplicado + _E > float(datos.importe):
        raise Rechazo(
            f"Ya imputaste ${aplicado:,.2f} de este anticipo: "
            "no podés bajar el importe",
            409,
        )
    for campo, valor in datos.model_dump().items():
        setattr(anticipo, campo, valor)
    anticipo.actualizado = datetime.utcnow()
    db.commit()
    db.refresh(anticipo)
    recalcular_estado(db, anticipo_id)
    return anticipo


def eliminar(db: Session, anticipo_id: int) -> None:
    anticipo = obtener(db, anticipo_id)
    if _suma(db, AplicacionAnticipo.anticipo_id == anticipo_id) > 0:
        raise Rechazo(
            "No se puede eliminar: el anticipo ya está imputado a facturas. "
            "Sacá esas aplicaciones primero.",
            409,
        )
    if anticipo.estado == "eliminado":
        raise Rechazo("Ese anticipo ya fue eliminado", 409)

    # No se borra la fila: queda marcada para que el estado de cuenta
    # muestre el movimiento contrario "Eliminación anticipos".
    anticipo.estado = "eliminado"
    anticipo.actualizado = datetime.utcnow()
    db.commit()
    db.refresh(anticipo)


# ------------------------------------------------------------ imputaciones
def _suma(db: Session, *condiciones) -> float:
    valor = (
        db.query(func.coalesce(func.sum(AplicacionAnticipo.importe), 0))
        .filter(*condiciones)
        .scalar()
    )
    return float(valor)


def aplicaciones(db: Session, anticipo_id: int) -> list[AplicacionAnticipo]:
    obtener(db, anticipo_id)
    return (
        db.query(AplicacionAnticipo)
        .filter(AplicacionAnticipo.anticipo_id == anticipo_id)
        .order_by(AplicacionAnticipo.id)
        .all()
    )


def recalcular_estado(db: Session, anticipo_id: int) -> str:
    """Estado = SUM de lo imputado. Nunca se suma en el navegador."""
    anticipo = obtener(db, anticipo_id)
    imputado = _suma(db, AplicacionAnticipo.anticipo_id == anticipo_id)
    importe = float(anticipo.importe)
    if imputado <= 0:
        estado = "disponible"
    elif imputado < importe - _E:
        estado = "parcial"
    else:
        estado = "aplicado"

    if anticipo.estado != estado:
        anticipo.estado = estado
        anticipo.actualizado = datetime.utcnow()
        db.commit()
        db.refresh(anticipo)
    return estado


def aplicar(
    db: Session, anticipo_id: int, datos: AplicacionAnticipoCrear
) -> AplicacionAnticipo:
    anticipo = obtener(db, anticipo_id)
    if anticipo.estado == "eliminado":
        raise Rechazo("No se puede imputar un anticipo eliminado", 409)
    factura = db.get(Factura, datos.factura_id)
    if factura is None:
        raise Rechazo("No existe esa factura", 404)
    if factura.cliente_id != anticipo.cliente_id:
        raise Rechazo("El anticipo y la factura son de clientes distintos", 409)
    if factura.estado == "anulada":
        raise Rechazo("No se le puede imputar nada a una factura anulada", 409)

    libre_anticipo = float(anticipo.importe) - _suma(
        db, AplicacionAnticipo.anticipo_id == anticipo_id
    )
    if datos.importe > libre_anticipo + _E:
        raise Rechazo(
            f"El anticipo {anticipo.numero} solo tiene ${libre_anticipo:,.2f} "
            "sin imputar",
            409,
        )

    libre_factura = float(factura.importe) - _suma(
        db, AplicacionAnticipo.factura_id == factura.id
    )
    if datos.importe > libre_factura + _E:
        raise Rechazo(
            f"La factura solo admite ${libre_factura:,.2f} más de imputación",
            409,
        )

    aplicacion = AplicacionAnticipo(
        anticipo_id=anticipo_id, factura_id=factura.id, importe=datos.importe
    )
    db.add(aplicacion)
    db.commit()
    db.refresh(aplicacion)
    recalcular_estado(db, anticipo_id)

    # la factura también cambia de estado: alguien la está pagando
    factura_service.recalcular_estado(db, factura.id)
    return aplicacion


def desaplicar(db: Session, aplicacion_id: int) -> None:
    aplicacion = db.get(AplicacionAnticipo, aplicacion_id)
    if aplicacion is None:
        raise Rechazo("No existe esa aplicación", 404)
    anticipo_id = aplicacion.anticipo_id
    factura_id = aplicacion.factura_id
    db.delete(aplicacion)
    db.commit()
    recalcular_estado(db, anticipo_id)
    factura_service.recalcular_estado(db, factura_id)


# --------------------------------------------------------------------- Excel

def informe_excel(anticipos: list[Anticipo], total_anticipado: float) -> bytes:
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Anticipos"

    columnas = [
        ("Fecha", 12),
        ("Número", 12),
        ("Cliente", 30),
        ("Importe", 14),
        ("Estado", 20),
    ]
    hoja.append([settings.nombre_estudio])
    hoja.cell(row=1, column=1).font = Font(bold=True, size=13)
    hoja.append([])

    hoja.append([nombre for nombre, _ in columnas])
    for celda in hoja[3]:
        celda.font = Font(bold=True)

    for a in anticipos:
        hoja.append(
            [
                a.fecha.isoformat(),
                a.numero,
                a.cliente_nombre,
                float(a.importe),
                ETIQUETAS_ESTADO.get(a.estado, a.estado),
            ]
        )

    hoja.append([""] * len(columnas))
    hoja.append(["", "", "TOTAL", total_anticipado])
    ultima = hoja.max_row
    hoja.cell(row=ultima, column=3).font = Font(bold=True)
    celda_total = hoja.cell(row=ultima, column=4)
    celda_total.font = Font(bold=True)
    celda_total.number_format = "#,##0.00"

    for (nombre, ancho), letra in zip(columnas, "ABCDE"):
        hoja.column_dimensions[letra].width = ancho

    salida = BytesIO()
    libro.save(salida)
    return salida.getvalue()


# ---------------------------------------------------------------------- PDF

def _pesos(valor: float) -> str:
    """60000.0 -> "60.000,00" (formato argentino, no el inglés)."""
    texto = f"{valor:,.2f}"
    miles, _punto, centavos = texto.rpartition(".")
    return f"{miles.replace(',', '.')},{centavos}"


def informe_pdf(
    anticipos: list[Anticipo],
    total_anticipado: float,
    alcance: str,
) -> bytes:
    """Informe en PDF.

    Las fuentes estándar de reportlab (Helvetica) se codifican en Latin-1,
    así que tildes, ñ y ° salen bien sin tocar nada raro.
    """
    buffer = BytesIO()
    documento = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title="Informe de anticipos",
    )

    estilos = getSampleStyleSheet()
    historias = [
        Paragraph(settings.nombre_estudio, estilos["Title"]),
        Paragraph("Informe de anticipos", estilos["Heading2"]),
        Spacer(1, 4 * mm),
        Paragraph(alcance, estilos["Normal"]),
        Spacer(1, 6 * mm),
    ]

    filas = [["FECHA", "N°", "CLIENTE", "IMPORTE", "ESTADO"]]
    for a in anticipos:
        filas.append(
            [
                a.fecha.strftime("%d/%m/%Y"),
                a.numero,
                a.cliente_nombre,
                _pesos(float(a.importe)),
                ETIQUETAS_ESTADO.get(a.estado, a.estado),
            ]
        )

    # 2,4 + 2,4 + 7,3 + 3,0 + 2,9 = 18 cm (A4 con margen de 1,5 a cada lado)
    tabla = Table(
        filas,
        colWidths=[2.4 * cm, 2.4 * cm, 7.3 * cm, 3.0 * cm, 2.9 * cm],
        repeatRows=1,
    )
    tabla.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#070b14")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                ("TOPPADDING", (0, 0), (-1, 0), 6),
                ("FONTSIZE", (0, 1), (-1, -1), 9),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#eef1f7")],
                ),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c9ced9")),
                ("ALIGN", (3, 0), (3, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 1), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
            ]
        )
    )
    historias.append(tabla)
    historias.append(Spacer(1, 6 * mm))

    # el total va a la derecha, justo debajo de la columna IMPORTE
    tabla_total = Table(
        [["TOTAL", _pesos(total_anticipado)]],
        colWidths=[12.1 * cm, 3.0 * cm],
    )
    tabla_total.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                ("LINEABOVE", (1, 0), (1, 0), 1, colors.HexColor("#070b14")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    historias.append(tabla_total)

    documento.build(historias)
    return buffer.getvalue()
