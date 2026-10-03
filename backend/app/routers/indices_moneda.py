from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_role
from app.database import get_db
from app.models.usuario import Usuario
from app.schemas.indice import IndiceCrear, IndiceOut
from app.services import indice_service

router = APIRouter(prefix="/indices-moneda", tags=["indices-moneda"])


@router.get("", response_model=list[IndiceOut])
def listar(
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return indice_service.listar(db)


@router.post("", response_model=IndiceOut, status_code=status.HTTP_201_CREATED)
def guardar(
    body: IndiceCrear,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return indice_service.guardar(db, body)


@router.delete("/{indice_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(
    indice_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    indice_service.eliminar(db, indice_id)
    return None
