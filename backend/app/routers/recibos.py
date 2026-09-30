from datetime import date

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_role
from app.database import get_db
from app.models.usuario import Usuario
from app.schemas.recibo import (
    AplicacionCrear,
    AplicacionOut,
    ETIQUETAS_FORMA,
    ReciboActualizar,
    ReciboCrear,
    ReciboOut,
)
from app.services import recibo_service

router = APIRouter(prefix="/recibos", tags=["recibos"])

_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("", response_model=list[ReciboOut])
def listar(
    cliente_id: int | None = Query(default=None),
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return recibo_service.listar(db, cliente_id=cliente_id, desde=desde, hasta=hasta)


# OJO: va ANTES de /{recibo_id} para que "export.xlsx" no se interprete como id.
@router.get("/export.xlsx")
def exportar(
    cliente_id: int | None = Query(default=None),
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Informe en Excel (.xlsx) con el total calculado por SQL."""
    recibos = recibo_service.listar(
        db, cliente_id=cliente_id, desde=desde, hasta=hasta
    )
    suma = recibo_service.total(
        db, cliente_id=cliente_id, desde=desde, hasta=hasta
    )
    contenido = recibo_service.informe_excel(recibos, suma)
    nombre = f"informe_recibos_{date.today().isoformat()}.xlsx"
    return Response(
        content=contenido,
        media_type=_XLSX,
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


@router.get("/total")
def total(
    cliente_id: int | None = Query(default=None),
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Suma de los importes filtrados — la hace SQL, nunca el navegador."""
    return {
        "total": recibo_service.total(
            db, cliente_id=cliente_id, desde=desde, hasta=hasta
        )
    }


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
