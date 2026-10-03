from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_role
from app.database import get_db
from app.models.usuario import Usuario
from app.schemas.tipogasto import TipoGastoCrear, TipoGastoOut
from app.services import tipogasto_service

router = APIRouter(prefix="/tipos-gasto", tags=["tipos-gasto"])


@router.get("", response_model=list[TipoGastoOut])
def listar(
    todos: bool = Query(default=False, description="Incluye los inactivos"),
    centro_id: int | None = Query(default=None, description="Solo los de ese centro"),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return tipogasto_service.listar(db, solo_activos=not todos, centro_id=centro_id)


@router.post("", response_model=TipoGastoOut, status_code=status.HTTP_201_CREATED)
def crear(
    body: TipoGastoCrear,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return tipogasto_service.crear(db, body)


@router.delete("/{tipo_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(
    tipo_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    tipogasto_service.eliminar(db, tipo_id)
    return None
