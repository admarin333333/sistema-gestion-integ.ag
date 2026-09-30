from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.localidad import Localidad
from app.models.usuario import Usuario
from app.schemas.localidad import LocalidadOut

router = APIRouter(prefix="/localidades", tags=["localidades"])


@router.get("", response_model=list[LocalidadOut])
def buscar(
    codigo_postal: str,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Localidades con ese código postal (4 dígitos).

    Si el CP no existe o no está cargado, devuelve lista vacía y el usuario
    escribe la localidad a mano.
    """
    cp = codigo_postal.strip()
    if not cp.isdigit() or len(cp) != 4:
        return []
    return (
        db.query(Localidad)
        .filter(Localidad.codigo_postal == cp)
        .order_by(Localidad.nombre)
        .all()
    )
