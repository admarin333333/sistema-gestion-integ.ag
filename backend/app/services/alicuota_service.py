from sqlalchemy.orm import Session

from app.core.errors import Rechazo
from app.models.alicuota import AlicuotaIva
from app.schemas.alicuota import AlicuotaCrear


def listar(db: Session, solo_activas: bool = True) -> list[AlicuotaIva]:
    consulta = db.query(AlicuotaIva)
    if solo_activas:
        consulta = consulta.filter(AlicuotaIva.activo.is_(True))
    return consulta.order_by(AlicuotaIva.porcentaje.asc()).all()


def obtener(db: Session, alicuota_id: int) -> AlicuotaIva:
    alicuota = db.get(AlicuotaIva, alicuota_id)
    if alicuota is None:
        raise Rechazo("No existe esa alícuota", 404)
    return alicuota


def crear(db: Session, datos: AlicuotaCrear) -> AlicuotaIva:
    existe = db.query(AlicuotaIva).filter(AlicuotaIva.nombre == datos.nombre).first()
    if existe:
        raise Rechazo(f"Ya existe la alícuota {datos.nombre}", 409)
    alicuota = AlicuotaIva(**datos.model_dump())
    db.add(alicuota)
    db.commit()
    db.refresh(alicuota)
    return alicuota


def eliminar(db: Session, alicuota_id: int) -> None:
    from app.models.cliente import Cliente

    alicuota = obtener(db, alicuota_id)
    en_uso = (
        db.query(Cliente).filter(Cliente.alicuota_iva_id == alicuota_id).first()
    )
    if en_uso:
        raise Rechazo(
            "No se puede eliminar: hay clientes usando esa alícuota",
            409,
        )
    db.delete(alicuota)
    db.commit()
