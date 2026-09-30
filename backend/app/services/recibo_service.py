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
    return (
        db.query(Recibo)
        .filter(*_condiciones(cliente_id, desde, hasta))
        .order_by(Recibo.fecha.desc(), Recibo.id.desc())
        .all()
    )


def total(
    db: Session, cliente_id: int | None = None, desde=None, hasta=None
) -> float:
    """Suma de importes — se calcula SIEMPRE con SQL, nunca en el navegador."""
    valor = (
        db.query(func.sum(Recibo.importe))
        .filter(*_condiciones(cliente_id, desde, hasta))
        .scalar()
    )
    return float(valor or 0)


def obtener(db: Session, recibo_id: int) -> Recibo:
    recibo = db.get(Recibo, recibo_id)
    if recibo is None:
        raise Rechazo("No existe ese recibo", 404)
    return recibo


def _verificar_unico(db: Session, numero: str, excluye: int | None = None) -> None:
    consulta = db.query(Recibo).filter(Recibo.numero == numero)
    if excluye:
        consulta = consulta.filter(Recibo.id != excluye)
    if consulta.first():
        raise Rechazo(f"Ya existe el recibo {numero}", 409)


def crear(db: Session, datos: ReciboCrear) -> Recibo:
    _verificar_unico(db, datos.numero)
    recibo = Recibo(**datos.model_dump())
    db.add(recibo)
    db.commit()
    db.refresh(recibo)
    return recibo


def actualizar(db: Session, recibo_id: int, datos: ReciboActualizar) -> Recibo:
    recibo = obtener(db, recibo_id)
    _verificar_unico(db, datos.numero, excluye=recibo_id)
    aplicado = _suma(db, Aplicacion.recibo_id == recibo_id)
    if aplicado + _E > float(datos.importe):
        raise Rechazo(
            f"Ya aplicaste ${aplicado:,.2f} de este recibo: no podés bajar el importe",
            409,
        )
    for campo, valor in datos.model_dump().items():
        setattr(recibo, campo, valor)
    recibo.actualizado = datetime.utcnow()
    db.commit()
    db.refresh(recibo)
    return recibo


def eliminar(db: Session, recibo_id: int) -> None:
    recibo = obtener(db, recibo_id)
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
