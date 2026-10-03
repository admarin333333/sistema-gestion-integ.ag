from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_role
from app.database import get_db
from app.models.usuario import Usuario
from app.schemas.centrocosto import CentroCostoCrear, CentroCostoOut
from app.services import centrocosto_service

router = APIRouter(prefix="/centros-costos", tags=["centros-costos"])


@router.get("", response_model=list[CentroCostoOut])
def listar(
    todos: bool = Query(default=False, description="Incluye los inactivos"),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return centrocosto_service.listar(db, solo_activos=not todos)


@router.post("", response_model=CentroCostoOut, status_code=status.HTTP_201_CREATED)
def crear(
    body: CentroCostoCrear,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return centrocosto_service.crear(db, body)


@router.delete("/{centro_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(
    centro_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    centrocosto_service.eliminar(db, centro_id)
    return None
