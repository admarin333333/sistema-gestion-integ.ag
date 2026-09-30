from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_role
from app.database import get_db
from app.models.usuario import Usuario
from app.schemas.recibo import (
    AplicacionCrear,
    AplicacionOut,
    ReciboActualizar,
    ReciboCrear,
    ReciboOut,
)
from app.services import recibo_service

router = APIRouter(prefix="/recibos", tags=["recibos"])


@router.get("", response_model=list[ReciboOut])
def listar(
    cliente_id: int | None = None,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return recibo_service.listar(db, cliente_id=cliente_id)


@router.post("", response_model=ReciboOut, status_code=status.HTTP_201_CREATED)
def crear(
    body: ReciboCrear,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return recibo_service.crear(db, body)


@router.get("/{recibo_id}", response_model=ReciboOut)
def obtener(
    recibo_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return recibo_service.obtener(db, recibo_id)


@router.put("/{recibo_id}", response_model=ReciboOut)
def actualizar(
    recibo_id: int,
    body: ReciboActualizar,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return recibo_service.actualizar(db, recibo_id, body)


@router.delete("/{recibo_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(
    recibo_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    recibo_service.eliminar(db, recibo_id)
    return None


# ------------------------------------------------------------- aplicaciones
@router.get("/{recibo_id}/aplicaciones", response_model=list[AplicacionOut])
def listar_aplicaciones(
    recibo_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return recibo_service.aplicaciones(db, recibo_id)


@router.post(
    "/{recibo_id}/aplicaciones",
    response_model=AplicacionOut,
    status_code=status.HTTP_201_CREATED,
)
def aplicar(
    recibo_id: int,
    body: AplicacionCrear,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return recibo_service.aplicar(db, recibo_id, body)


@router.delete("/aplicaciones/{aplicacion_id}", status_code=status.HTTP_204_NO_CONTENT)
def desaplicar(
    aplicacion_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    recibo_service.desaplicar(db, aplicacion_id)
    return None
