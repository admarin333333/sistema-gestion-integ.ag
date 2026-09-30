from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_role
from app.database import get_db
from app.models.usuario import Usuario
from app.schemas.sugerencia import SugerenciaActualizar, SugerenciaOut
from app.services import sugerencia_service

router = APIRouter(prefix="/sugerencias", tags=["sugerencias"])


@router.put("/{sugerencia_id}", response_model=SugerenciaOut)
def actualizar(
    sugerencia_id: int,
    body: SugerenciaActualizar,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return sugerencia_service.actualizar(db, sugerencia_id, body)


@router.delete("/{sugerencia_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(
    sugerencia_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    sugerencia_service.eliminar(db, sugerencia_id)
    return None
