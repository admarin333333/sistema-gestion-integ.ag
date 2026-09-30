from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_role
from app.database import get_db
from app.models.cliente import Cliente
from app.models.usuario import Usuario
from app.schemas.cliente import ClienteActualizar, ClienteCrear, ClienteOut
from app.schemas.recibo import CuentaCorrienteOut
from app.schemas.sugerencia import SugerenciaCrear, SugerenciaOut
from app.services import cliente_service, cuenta_service, sugerencia_service

router = APIRouter(prefix="/clientes", tags=["clientes"])


@router.get("", response_model=list[ClienteOut])
def listar(
    q: str | None = Query(default=None, description="Busca por nombre, DNI o CUIT"),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return cliente_service.listar(db, q)


@router.post("", response_model=ClienteOut, status_code=status.HTTP_201_CREATED)
def crear(
    body: ClienteCrear,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return cliente_service.crear(db, body)


@router.get("/{cliente_id}", response_model=ClienteOut)
def obtener(
    cliente_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return cliente_service.obtener(db, cliente_id)


@router.put("/{cliente_id}", response_model=ClienteOut)
def actualizar(
    cliente_id: int,
    body: ClienteActualizar,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return cliente_service.actualizar(db, cliente_id, body)


@router.delete("/{cliente_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(
    cliente_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    cliente_service.eliminar(db, cliente_id)
    return None


@router.get("/{cliente_id}/sugerencias", response_model=list[SugerenciaOut])
def listar_sugerencias(
    cliente_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    cliente_service.obtener(db, cliente_id)
    return sugerencia_service.listar(db, cliente_id)


@router.post(
    "/{cliente_id}/sugerencias",
    response_model=SugerenciaOut,
    status_code=status.HTTP_201_CREATED,
)
def crear_sugerencia(
    cliente_id: int,
    body: SugerenciaCrear,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    cliente_service.obtener(db, cliente_id)
    return sugerencia_service.crear(db, cliente_id, body)


@router.get("/{cliente_id}/cuenta-corriente", response_model=CuentaCorrienteOut)
def cuenta_corriente(
    cliente_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Historial DEBE · HABER · SALDO del cliente."""
    return cuenta_service.movimientos(db, cliente_id)
