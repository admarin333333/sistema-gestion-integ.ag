from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_role
from app.database import get_db
from app.models.usuario import Usuario
from app.schemas.alicuota import AlicuotaCrear, AlicuotaOut
from app.services import alicuota_service

router = APIRouter(prefix="/alicuotas-iva", tags=["alicuotas-iva"])


@router.get("", response_model=list[AlicuotaOut])
def listar(
    todas: bool = Query(default=False, description="Incluye las inactivas"),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return alicuota_service.listar(db, solo_activas=not todas)


@router.post("", response_model=AlicuotaOut, status_code=status.HTTP_201_CREATED)
def crear(
    body: AlicuotaCrear,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return alicuota_service.crear(db, body)


@router.delete("/{alicuota_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(
    alicuota_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    alicuota_service.eliminar(db, alicuota_id)
    return None
