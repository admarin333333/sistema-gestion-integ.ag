from fastapi import APIRouter, Body, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_role
from app.database import get_db
from app.models.usuario import Usuario
from app.schemas.plan_cuenta import (
    PlanCuentaCrear,
    PlanCuentaEditar,
    PlanCuentaOut,
)
from app.services import plan_cuenta_service

router = APIRouter(prefix="/plan-cuentas", tags=["plan-cuentas"])


@router.get("", response_model=list[PlanCuentaOut])
def listar(
    todas: bool = Query(default=False, description="Incluye las apagadas"),
    q: str = Query(default="", description="Buscar por código o nombre"),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """El plan de cuentas completo, para armar el árbol en pantalla."""
    return plan_cuenta_service.listar(db, solo_activas=not todas, buscar=q)


@router.get("/{cuenta_id}", response_model=PlanCuentaOut)
def obtener(
    cuenta_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return plan_cuenta_service.obtener(db, cuenta_id)


@router.post("", response_model=PlanCuentaOut, status_code=status.HTTP_201_CREATED)
def crear(
    body: PlanCuentaCrear,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    """Agrega una cuenta nueva colgando de otra. El código lo arma el sistema."""
    return plan_cuenta_service.crear(
        db,
        cuenta_padre_id=body.cuenta_padre_id,
        nombre=body.nombre,
        imputable=body.imputable,
        tipo_auxiliar=body.tipo_auxiliar,
    )


@router.put("/{cuenta_id}", response_model=PlanCuentaOut)
def editar(
    cuenta_id: int,
    body: PlanCuentaEditar,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    """Renombra, cambia el tipo de auxiliar o apaga. El código no se toca."""
    return plan_cuenta_service.editar(
        db,
        cuenta_id,
        nombre=body.nombre,
        imputable=body.imputable,
        tipo_auxiliar=body.tipo_auxiliar,
        activa=body.activa,
    )


@router.delete("/{cuenta_id}", status_code=status.HTTP_204_NO_CONTENT)
def apagar(
    cuenta_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    """Apaga una cuenta de detalle. Si tiene subcuentas, no se puede."""
    plan_cuenta_service.eliminar(db, cuenta_id)
    return None