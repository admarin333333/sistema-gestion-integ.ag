from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response

from app.core.deps import get_current_user, require_role
from app.database import get_db
from app.models.usuario import Usuario
from app.schemas.balance_rt54 import (
    BalanceGuardar,
    CuadrosRecalcular,
    EjercicioCrear,
)
from app.services import balance_rt54_service

router = APIRouter(prefix="/balance-rt54", tags=["balance-rt54"])

_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/ejercicios")
def listar(
    cliente_id: int = Query(..., description="Cliente dueño de los balances"),
    db=Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Ejercicios de estados contables de un cliente (la tabla de balances)."""
    return balance_rt54_service.listar_ejercicios(db, cliente_id)


@router.post("/ejercicios", status_code=status.HTTP_201_CREATED)
def crear(
    body: EjercicioCrear,
    db=Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Crea un ejercicio con la carátula copiada de la ficha del cliente."""
    return balance_rt54_service.crear(db, body)


@router.get("/ejercicios/{ejercicio_id}")
def obtener(
    ejercicio_id: int,
    db=Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Los tres estados (con los totales ya calculados en el backend)."""
    return balance_rt54_service.obtener(db, ejercicio_id)


@router.put("/ejercicios/{ejercicio_id}")
def guardar(
    ejercicio_id: int,
    body: BalanceGuardar,
    db=Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Guarda carátula e importes; devuelve todo recalculado."""
    return balance_rt54_service.guardar(db, ejercicio_id, body)


@router.post("/cuadros-notas")
def recalcular_cuadros(
    body: CuadrosRecalcular,
    user: Usuario = Depends(get_current_user),
):
    """Sumatorias de los cuadros de notas con estos importes (sin guardar)."""
    return balance_rt54_service.recalcular_cuadros(body.celdas_nota)


@router.delete("/ejercicios/{ejercicio_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(
    ejercicio_id: int,
    db=Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    balance_rt54_service.eliminar(db, ejercicio_id)
    return None


@router.get("/ejercicios/{ejercicio_id}/export.xlsx")
def exportar(
    ejercicio_id: int,
    db=Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Emite el Excel del modelo RT54 con los datos cargados."""
    nombre, contenido = balance_rt54_service.exportar_excel(db, ejercicio_id)
    return Response(
        content=contenido,
        media_type=_XLSX,
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


@router.get("/ejercicios/{ejercicio_id}/moneda-homogenea")
def moneda_homogenea(
    ejercicio_id: int,
    db=Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Balance al cierre actualizado con el índice FACPCE (sin guardar)."""
    return balance_rt54_service.moneda_homogenea(db, ejercicio_id)


@router.get("/ejercicios/{ejercicio_id}/moneda-homogenea.xlsx")
def exportar_moneda_homogenea(
    ejercicio_id: int,
    db=Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Excel aparte con el balance actualizado por moneda homogénea."""
    nombre, contenido = balance_rt54_service.exportar_moneda_homogenea(db, ejercicio_id)
    return Response(
        content=contenido,
        media_type=_XLSX,
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )
