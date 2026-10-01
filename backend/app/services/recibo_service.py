from datetime import datetime
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.core.errors import Rechazo
from app.models.factura import Factura
from app.models.recibo import Aplicacion, Recibo
from app.schemas.recibo import (
    AplicacionCrear,
    ETIQUETAS_ESTADO,
    ETIQUETAS_FORMA,
    ReciboActualizar,
    ReciboCrear,
)
from app.services import factura_service

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


def listar(
    db: Session, cliente_id: int | None = None, desde=None, hasta=None
) -> list[Recibo]:
    """Lista TODOS los recibos (emitidos y anulados) para que se vean en el listado."""
    return (
        db.query(Recibo)
        .filter(*_condiciones(cliente_id, desde, hasta))
        .order_by(Recibo.fecha.desc(), Recibo.id.desc())
        .all()
    )


def total(
    db: Session, cliente_id: int | None = None, desde=None, hasta=None
) -> float:
    """Suma de importes — se calcula SIEMPRE con SQL, nunca en el navegador.
    Solo suma los emitidos (no los anulados)."""
    condiciones = _condiciones(cliente_id, desde, hasta)
    condiciones.append(Recibo.estado == "emitido")
    valor = (
        db.query(func.sum(Recibo.importe))
        .filter(*condiciones)
        .scalar()
    )
    return float(valor or 0)


def obtener(db: Session, recibo_id: int) -> Recibo:
    recibo = db.get(Recibo, recibo_id)
    if recibo is None:
        raise Rechazo("No existe ese recibo", 404)
    return recibo


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


def _verificar_unico(db: Session, numero: str, excluye: int | None = None) -> None:
    consulta = db.query(Recibo).filter(Recibo.numero == numero)
    if excluye:
        consulta = consulta.filter(Recibo.id != excluye)
    if consulta.first():
        raise Rechazo(f"Ya existe el recibo {numero}", 409)


def crear(db: Session, datos: ReciboCrear) -> Recibo:
    # Generar número correlativo automáticamente
    numero = _proximo_numero(db)
    datos_dict = datos.model_dump()
    datos_dict["numero"] = numero
    recibo = Recibo(**datos_dict)
    db.add(recibo)
    db.commit()
    db.refresh(recibo)
    return recibo


def actualizar(db: Session, recibo_id: int, datos: ReciboActualizar) -> Recibo:
    recibo = obtener(db, recibo_id)
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
    if recibo.estado == "emitido":
        raise Rechazo("El recibo ya está emitido", 409)
    recibo.estado = "emitido"
    recibo.actualizado = datetime.utcnow()
    db.commit()
    db.refresh(recibo)
    return recibo


def eliminar(db: Session, recibo_id: int) -> None:
    recibo = obtener(db, recibo_id)
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
