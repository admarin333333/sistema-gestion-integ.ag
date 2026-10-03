from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.usuario import Usuario
from app.services import propietario_service

router = APIRouter(prefix="/propietario", tags=["propietario"])


@router.get("")
def obtener(
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Datos del propietario del software (una sola fila)."""
    return propietario_service.a_json(propietario_service.obtener(db))


@router.put("")
def guardar(
    body: dict = Body(...),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Guarda los datos del propietario."""
    p = propietario_service.guardar(db, body)
    return propietario_service.a_json(p)