from datetime import date

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_role
from app.database import get_db
from app.models.usuario import Usuario
from app.schemas.factura import (
    EnvioMasivo,
    EnvioResultado,
    FacturaActualizar,
    FacturaCrear,
    FacturaOut,
)
from app.services import factura_service, mail_service

router = APIRouter(prefix="/facturas", tags=["facturas"])

_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("", response_model=list[FacturaOut])
def listar(
    cliente_id: int | None = Query(default=None),
    estado: str | None = Query(default=None),
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return factura_service.listar(
        db, cliente_id=cliente_id, estado=estado, desde=desde, hasta=hasta,
        descendente=True,
    )


# OJO: va ANTES de /{factura_id} para que "export.xlsx" no se interprete como id.
@router.get("/export.xlsx")
def exportar(
    cliente_id: int | None = Query(default=None),
    estado: str | None = Query(default=None),
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Informe en Excel (.xlsx) con el total calculado por SQL."""
    facturas = factura_service.listar(
        db, cliente_id=cliente_id, estado=estado, desde=desde, hasta=hasta
    )
    suma = factura_service.total(
        db, cliente_id=cliente_id, estado=estado, desde=desde, hasta=hasta
    )
    contenido = factura_service.informe_excel(facturas, suma)
    nombre = f"informe_facturas_{date.today().isoformat()}.xlsx"
    return Response(
        content=contenido,
        media_type=_XLSX,
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


@router.get("/total")
def total(
    cliente_id: int | None = Query(default=None),
    estado: str | None = Query(default=None),
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Suma de los importes filtrados — la hace SQL, nunca el navegador."""
    return {
        "total": factura_service.total(
            db, cliente_id=cliente_id, estado=estado, desde=desde, hasta=hasta
        )
    }


@router.get("/{factura_id}/pdf")
def descargar_pdf(
    factura_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """El comprobante en PDF — es lo que va adjunto en el mail al cliente."""
    contenido = factura_service.pdf(db, factura_id)
    return Response(
        content=contenido,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="comprobante.pdf"',
        },
    )


@router.post("", response_model=FacturaOut, status_code=status.HTTP_201_CREATED)
def crear(
    body: FacturaCrear,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    # el mail NO se manda acá: se manda con el botón "Enviar por mail"
    return factura_service.crear(db, body)


@router.post("/enviar", response_model=EnvioResultado)
def enviar(
    body: EnvioMasivo,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Manda una o varias facturas por mail, con el PDF adjunto."""
    enviadas, avisos = mail_service.enviar_varias(db, body.ids)
    return {"enviadas": enviadas, "avisos": avisos}


@router.get("/{factura_id}", response_model=FacturaOut)
def obtener(
    factura_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return factura_service.obtener(db, factura_id)


@router.put("/{factura_id}", response_model=FacturaOut)
def actualizar(
    factura_id: int,
    body: FacturaActualizar,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return factura_service.actualizar(db, factura_id, body)


@router.post("/{factura_id}/anular", response_model=FacturaOut)
def anular(
    factura_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    return factura_service.anular(db, factura_id)


@router.post("/{factura_id}/reabrir", response_model=FacturaOut)
def reabrir(
    factura_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    return factura_service.reabrir(db, factura_id)


@router.delete("/{factura_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(
    factura_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    factura_service.eliminar(db, factura_id)
    return None
