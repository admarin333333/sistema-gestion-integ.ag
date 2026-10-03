from datetime import date

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_role
from app.core.errors import Rechazo
from app.database import get_db
from app.models.usuario import Usuario
from app.schemas.compra import (
    CompraActualizar,
    CompraCrear,
    CompraOut,
    CompraPreviewIn,
)
from app.services import asiento_automatico, asiento_service, compra_service

router = APIRouter(prefix="/compras", tags=["compras"])

_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("", response_model=list[CompraOut])
def listar(
    proveedor_id: int | None = Query(default=None),
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    sin_asiento: bool = Query(
        default=False, description="Solo las que todavía no están en los libros"
    ),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return compra_service.listar(
        db,
        proveedor_id=proveedor_id,
        desde=desde,
        hasta=hasta,
        sin_asiento=sin_asiento,
    )


# OJO: van ANTES de /{compra_id} para que no se interpreten como id.
@router.get("/export.xlsx")
def exportar(
    proveedor_id: int | None = Query(default=None),
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Informe en Excel (.xlsx) con el total calculado por SQL."""
    compras = compra_service.listar(
        db, proveedor_id=proveedor_id, desde=desde, hasta=hasta
    )
    suma = compra_service.total(
        db, proveedor_id=proveedor_id, desde=desde, hasta=hasta
    )
    contenido = compra_service.informe_excel(compras, suma)
    nombre = f"informe_compras_{date.today().isoformat()}.xlsx"
    return Response(
        content=contenido,
        media_type=_XLSX,
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


@router.get("/total")
def total(
    proveedor_id: int | None = Query(default=None),
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Suma de los totales filtrados — la hace SQL, nunca el navegador."""
    return {
        "total": compra_service.total(
            db, proveedor_id=proveedor_id, desde=desde, hasta=hasta
        )
    }


@router.post("", response_model=CompraOut, status_code=status.HTTP_201_CREATED)
def crear(
    body: CompraCrear,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return compra_service.crear(db, body)


@router.get("/{compra_id}", response_model=CompraOut)
def obtener(
    compra_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return compra_service.obtener(db, compra_id)


@router.put("/{compra_id}", response_model=CompraOut)
def actualizar(
    compra_id: int,
    body: CompraActualizar,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return compra_service.actualizar(db, compra_id, body)


@router.post("/{compra_id}/anular", response_model=CompraOut)
def anular(
    compra_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    return compra_service.anular(db, compra_id)


@router.post("/{compra_id}/reabrir", response_model=CompraOut)
def reabrir(
    compra_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    return compra_service.reabrir(db, compra_id)


# --- el asiento ---------------------------------------------------------
# La compra se guarda al cargarla; el asiento es un botón aparte, igual que
# en las facturas y los recibos. Cargar una compra NO mueve la cuenta: hasta
# que no se asienta, el gasto no aparece en el informe por centro de costos.


@router.post("/preview-asiento")
def preview_asiento(
    body: CompraPreviewIn,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """El asiento que VA a quedar, sin guardar nada.

    Usa la misma función que el asiento real (`proyectar_compra`): si el
    preview y el asiento hicieran la cuenta cada uno por su lado, la pantalla
    mostraría una cosa y se guardaría otra.
    """
    return asiento_automatico.proyectar_compra(
        db,
        fecha=body.fecha,
        tipo_comprobante=body.tipo_comprobante,
        punto_venta=body.punto_venta,
        numero=body.numero,
        concepto=body.concepto,
        neto=body.neto,
        iva=body.iva,
        percepcion=body.percepcion_iva,
        total=body.total,
        cuenta_gasto_id=body.cuenta_gasto_id,
        proveedor_id=body.proveedor_id,
        proveedor_nombre=body.proveedor_nombre or "",
    )


@router.post("/{compra_id}/asiento")
def generar_asiento(
    compra_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    """Genera y contabiliza el asiento de la compra.

    Admin solamente: mueve los libros. Un operador carga la compra (que no
    mueve nada) pero no la asienta.
    """
    return asiento_automatico.asiento_de_compra(db, compra_id)


@router.post("/{compra_id}/asiento/anular")
def anular_asiento(
    compra_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    """Anula el asiento de la compra. La compra queda como estaba.

    Anular el asiento NO anula la compra: son dos cosas distintas, como con las
    facturas. La compra sigue su curso y se puede reasentar.
    """
    compra = compra_service.obtener(db, compra_id)
    if not getattr(compra, "id_asiento", None):
        raise Rechazo("La compra no tiene asiento: no hay nada que anular", 409)
    asiento_service.anular(db, compra.id_asiento)
    return compra_service.obtener(db, compra_id)


@router.delete("/{compra_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(
    compra_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    compra_service.eliminar(db, compra_id)
    return None
