from sqlalchemy.orm import Session

from app.core.errors import Rechazo
from app.models.centrocosto import CentroCosto
from app.schemas.centrocosto import CentroCostoCrear


def listar(db: Session, solo_activos: bool = True) -> list[CentroCosto]:
    consulta = db.query(CentroCosto)
    if solo_activos:
        consulta = consulta.filter(CentroCosto.activo.is_(True))
    return consulta.order_by(CentroCosto.nombre.asc()).all()


def obtener(db: Session, centro_id: int) -> CentroCosto:
    centro = db.get(CentroCosto, centro_id)
    if centro is None:
        raise Rechazo("No existe ese centro de costos", 404)
    return centro


def crear(db: Session, datos: CentroCostoCrear) -> CentroCosto:
    existe = db.query(CentroCosto).filter(CentroCosto.nombre == datos.nombre).first()
    if existe:
        raise Rechazo(f"Ya existe el centro {datos.nombre}", 409)
    centro = CentroCosto(**datos.model_dump())
    db.add(centro)
    db.commit()
    db.refresh(centro)
    return centro


def eliminar(db: Session, centro_id: int) -> None:
    centro = obtener(db, centro_id)
    # Cuando exista el módulo de compras, acá se bloquea si tiene
    # comprobantes imputados (igual que alicuotas con clientes).
    db.delete(centro)
    db.commit()
