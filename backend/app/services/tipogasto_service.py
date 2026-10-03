from sqlalchemy.orm import Session

from app.core.errors import Rechazo
from app.models.centrocosto import CentroCosto
from app.models.tipogasto import TipoGasto
from app.schemas.tipogasto import TipoGastoCrear


def listar(
    db: Session, solo_activos: bool = True, centro_id: int | None = None
) -> list[TipoGasto]:
    consulta = db.query(TipoGasto)
    if solo_activos:
        consulta = consulta.filter(TipoGasto.activo.is_(True))
    if centro_id is not None:
        consulta = consulta.filter(TipoGasto.centro_costo_id == centro_id)
    return consulta.order_by(TipoGasto.nombre.asc()).all()


def obtener(db: Session, tipo_id: int) -> TipoGasto:
    tipo = db.get(TipoGasto, tipo_id)
    if tipo is None:
        raise Rechazo("No existe ese tipo de gasto", 404)
    return tipo


def crear(db: Session, datos: TipoGastoCrear) -> TipoGasto:
    existe = db.query(TipoGasto).filter(TipoGasto.nombre == datos.nombre).first()
    if existe:
        raise Rechazo(f"Ya existe el tipo de gasto {datos.nombre}", 409)
    centro = db.get(CentroCosto, datos.centro_costo_id)
    if centro is None or not centro.activo:
        raise Rechazo("Elegí un centro de costos válido", 409)
    tipo = TipoGasto(**datos.model_dump())
    db.add(tipo)
    db.commit()
    db.refresh(tipo)
    return tipo


def eliminar(db: Session, tipo_id: int) -> None:
    tipo = obtener(db, tipo_id)
    # Cuando exista el módulo de compras, acá se bloquea si tiene
    # comprobantes imputados (igual que alicuotas con clientes).
    db.delete(tipo)
    db.commit()
