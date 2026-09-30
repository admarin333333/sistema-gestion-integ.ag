from sqlalchemy.orm import Session

from app.core.errors import Rechazo
from app.models.sugerencia import Sugerencia
from app.schemas.sugerencia import SugerenciaCrear, SugerenciaActualizar


def listar(db: Session, cliente_id: int) -> list[Sugerencia]:
    return (
        db.query(Sugerencia)
        .filter(Sugerencia.cliente_id == cliente_id)
        .order_by(Sugerencia.fecha.desc(), Sugerencia.id.desc())
        .all()
    )


def crear(db: Session, cliente_id: int, datos: SugerenciaCrear) -> Sugerencia:
    sugerencia = Sugerencia(**datos.model_dump(), cliente_id=cliente_id)
    db.add(sugerencia)
    db.commit()
    db.refresh(sugerencia)
    return sugerencia


def actualizar(
    db: Session, sugerencia_id: int, datos: SugerenciaActualizar
) -> Sugerencia:
    sugerencia = db.get(Sugerencia, sugerencia_id)
    if sugerencia is None:
        raise Rechazo("No existe esa sugerencia", 404)
    for campo, valor in datos.model_dump().items():
        setattr(sugerencia, campo, valor)
    db.commit()
    db.refresh(sugerencia)
    return sugerencia


def eliminar(db: Session, sugerencia_id: int) -> None:
    sugerencia = db.get(Sugerencia, sugerencia_id)
    if sugerencia is None:
        raise Rechazo("No existe esa sugerencia", 404)
    db.delete(sugerencia)
    db.commit()
