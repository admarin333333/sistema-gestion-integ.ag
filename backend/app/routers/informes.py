from datetime import date
from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.usuario import Usuario
from app.services import informes_service

router = APIRouter(prefix="/informes", tags=["informes"])

_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/estado-deuda")
def estado_deuda(
    cliente_id: int | None = Query(default=None),
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Estado de deuda total: facturas, notas de crédito, notas de débito pendientes."""
    return informes_service.informe_estado_deuda(db, desde=desde, hasta=hasta, cliente_id=cliente_id)


@router.get("/estado-deuda/export.xlsx")
def exportar_estado_deuda(
    cliente_id: int | None = Query(default=None),
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Estado de deuda en Excel."""
    data = informes_service.informe_estado_deuda(db, desde=desde, hasta=hasta, cliente_id=cliente_id)
    contenido = informes_service.estado_deuda_excel(data)
    nombre = f"estado_deuda_{date.today().isoformat()}.xlsx"
    return Response(
        content=contenido,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


@router.get("/anticipos-pendientes")
def anticipos_pendientes(
    cliente_id: int | None = Query(default=None),
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Listado de anticipos pendientes de imputación (disponible/parcial)."""
    return informes_service.informe_anticipos_pendientes(db, desde=desde, hasta=hasta, cliente_id=cliente_id)


@router.get("/anticipos-pendientes/export.xlsx")
def exportar_anticipos_pendientes(
    cliente_id: int | None = Query(default=None),
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Anticipos pendientes en Excel."""
    data = informes_service.informe_anticipos_pendientes(db, desde=desde, hasta=hasta, cliente_id=cliente_id)
    contenido = informes_service.anticipos_pendientes_excel(data)
    nombre = f"anticipos_pendientes_{date.today().isoformat()}.xlsx"
    return Response(
        content=contenido,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )