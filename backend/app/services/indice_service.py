"""Índices de moneda homogénea: alta manual, corrección y baja."""

from datetime import date

from sqlalchemy.orm import Session

from app.core.errors import Rechazo
from app.models.indice import IndiceMoneda
from app.schemas.indice import IndiceCrear


def listar(db: Session) -> list[IndiceMoneda]:
    return (
        db.query(IndiceMoneda)
        .order_by(IndiceMoneda.fecha.desc(), IndiceMoneda.id.desc())
        .all()
    )


def guardar(db: Session, datos: IndiceCrear) -> IndiceMoneda:
    """Si el mes ya tiene índice, lo corrige; si no, lo da de alta."""
    # El índice corresponde al mes completo: normalizamos al día 1.
    mes = date(datos.fecha.year, datos.fecha.month, 1)
    fila = db.query(IndiceMoneda).filter(IndiceMoneda.fecha == mes).first()
    if fila:
        fila.indice = datos.indice
    else:
        fila = IndiceMoneda(fecha=mes, indice=datos.indice)
        db.add(fila)
    db.commit()
    db.refresh(fila)
    return fila


def eliminar(db: Session, indice_id: int) -> None:
    fila = db.get(IndiceMoneda, indice_id)
    if fila is None:
        raise Rechazo("No existe ese índice", 404)
    db.delete(fila)
    db.commit()


def del_mes(db: Session, fecha: date) -> IndiceMoneda | None:
    """Índice del mes al que pertenece `fecha` (o None si falta cargarlo)."""
    return (
        db.query(IndiceMoneda)
        .filter(IndiceMoneda.fecha == date(fecha.year, fecha.month, 1))
        .first()
    )
