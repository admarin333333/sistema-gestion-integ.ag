from datetime import date

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_role
from app.database import get_db
from app.models.usuario import Usuario
from app.schemas.anticipo import (
    AnticipoActualizar,
    AnticipoCrear,
    AnticipoOut,
    AplicacionAnticipoCrear,
    AplicacionAnticipoOut,
)
from app.services import anticipo_service, cliente_service

router = APIRouter(prefix="/anticipos", tags=["anticipos"])

_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_PDF = "application/pdf"


@router.get("", response_model=list[AnticipoOut])
def listar(
    cliente_id: int | None = None,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return anticipo_service.listar(db, cliente_id=cliente_id)


def _alcance(db: Session, cliente_id: int | None, desde, hasta) -> str:
    """Qué cubre el informe, para que el papel se explique solo."""
    partes = []
    if cliente_id:
        cliente = cliente_service.obtener(db, cliente_id)
        partes.append(f"Cliente: {cliente.nombre_completo}")
    if desde:
        partes.append(f"Desde: {desde.strftime('%d/%m/%Y')}")
    if hasta:
        partes.append(f"Hasta: {hasta.strftime('%d/%m/%Y')}")
    partes.append(f"Generado: {date.today().strftime('%d/%m/%Y')}")
    return "  ·  ".join(partes)


# OJO: van ANTES de /{anticipo_id} para que "informe.pdf" no se interprete
# como si fuera un id.
@router.get("/informe.xlsx")
def exportar(
    cliente_id: int | None = Query(default=None),
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Listado en Excel: encabezado, nombres de columna y total abajo."""
    anticipos = anticipo_service.listar(
        db, cliente_id=cliente_id, desde=desde, hasta=hasta
    )
    suma = anticipo_service.total(db, cliente_id=cliente_id, desde=desde, hasta=hasta)
    contenido = anticipo_service.informe_excel(anticipos, suma)
    nombre = f"informe_anticipos_{date.today().isoformat()}.xlsx"
    return Response(
        content=contenido,
        media_type=_XLSX,
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


@router.get("/informe.pdf")
def informe(
    cliente_id: int | None = Query(default=None),
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Listado en PDF: encabezado, nombres de columna y total abajo."""
    anticipos = anticipo_service.listar(
        db, cliente_id=cliente_id, desde=desde, hasta=hasta
    )
    suma = anticipo_service.total(db, cliente_id=cliente_id, desde=desde, hasta=hasta)
    contenido = anticipo_service.informe_pdf(
        anticipos, suma, _alcance(db, cliente_id, desde, hasta)
    )
    nombre = f"informe_anticipos_{date.today().isoformat()}.pdf"
    return Response(
        content=contenido,
        media_type=_PDF,
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


@router.post("", response_model=AnticipoOut, status_code=status.HTTP_201_CREATED)
def crear(
    body: AnticipoCrear,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return anticipo_service.crear(db, body)


@router.get("/{anticipo_id}", response_model=AnticipoOut)
def obtener(
    anticipo_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return anticipo_service.obtener(db, anticipo_id)


@router.put("/{anticipo_id}", response_model=AnticipoOut)
def actualizar(
    anticipo_id: int,
    body: AnticipoActualizar,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return anticipo_service.actualizar(db, anticipo_id, body)


@router.delete("/{anticipo_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(
    anticipo_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    anticipo_service.eliminar(db, anticipo_id)
    return None


# ------------------------------------------------------------ imputaciones
@router.get("/{anticipo_id}/aplicaciones", response_model=list[AplicacionAnticipoOut])
def listar_aplicaciones(
    anticipo_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return anticipo_service.aplicaciones(db, anticipo_id)


@router.post(
    "/{anticipo_id}/aplicaciones",
    response_model=AplicacionAnticipoOut,
    status_code=status.HTTP_201_CREATED,
)
def aplicar(
    anticipo_id: int,
    body: AplicacionAnticipoCrear,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return anticipo_service.aplicar(db, anticipo_id, body)


@router.delete(
    "/aplicaciones/{aplicacion_id}", status_code=status.HTTP_204_NO_CONTENT
)
def desaplicar(
    aplicacion_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    anticipo_service.desaplicar(db, aplicacion_id)
    return None
