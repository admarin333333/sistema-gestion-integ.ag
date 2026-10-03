from fastapi import APIRouter, Depends, Query, status

from app.core.deps import get_current_user
from app.database import get_db
from app.models.usuario import Usuario
from app.schemas.variante import VarianteCrear, VarianteOut
from app.services import variante_service

router = APIRouter(prefix="/variantes", tags=["variantes"])


@router.get("", response_model=list[VarianteOut])
def listar(
    pantalla: str = Query(..., description="Pantalla dueña de las variantes"),
    db=Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Variantes propias + compartidas de esa pantalla."""
    return variante_service.listar(db, pantalla, user)


@router.post("", response_model=VarianteOut, status_code=status.HTTP_201_CREATED)
def guardar(
    body: VarianteCrear,
    db=Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Guarda (o sobreescribe) una variante propia."""
    return variante_service.guardar(db, body, user)


@router.delete("/{variante_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(
    variante_id: int,
    db=Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    variante_service.eliminar(db, variante_id, user)
    return None
