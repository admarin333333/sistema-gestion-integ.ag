from datetime import date

from fastapi import APIRouter, Body, Depends, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_role
from app.database import get_db
from app.models.usuario import Usuario
from app.schemas.recibo import (
    AplicacionCrear,
    AplicacionOut,
    CobroPreviewIn,
    ETIQUETAS_FORMA,
    FormaPagoConfigOut,
    PagoIn,
    PagoOut,
    ReciboActualizar,
    ReciboCrear,
    ReciboOut,
)
from app.services import recibo_service

router = APIRouter(prefix="/recibos", tags=["recibos"])

_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


# =============================================================================
# FORMAS DE PAGO Y PAGOS
#
# OJO con el orden: FastAPI evalúa las rutas EN ORDEN, así que las fijas
# ("/formas-pago") tienen que ir ANTES que las que llevan `{recibo_id}`. Si no,
# "formas-pago" entra por el parámetro y Pydantic lo lee como un número (el
# mismo error que pasaba con /ejercicios/cuenta-cobro-fija).
# =============================================================================


@router.get("/formas-pago", response_model=list[FormaPagoConfigOut])
def formas_pago(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    """A qué cuenta va cada forma de pago, y cuáles necesitan que elijas el banco.

    Sale de `config_cuentas_forma_pago`, que es una TABLA: si el estudio cambia
    de banco, se cambia ahí y no hay que tocar el programa.
    """
    return recibo_service.formas_pago(db)


@router.get("/cuentas-ingreso")
def cuentas_ingreso(
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Las cuentas donde puede entrar la plata (cajas y bancos), para el desplegable.

    No la lista entera del plan de cuentas: de las 200, casi ninguna sirve para
    un cobro (no se deposita un cheque en "costo por venta").
    """
    return recibo_service.cuentas_ingreso(db)


@router.post("/preview-cobro")
def preview_cobro(
    body: CobroPreviewIn,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Muestra cómo quedaría el recibo y su asiento, SIN guardar nada.

    Es el paso 4 de la pantalla: el contador ve el recibo armado y el Debe/Haber
    antes de confirmar. Lo que sale de acá es exactamente lo que se guarda,
    porque usa las mismas dos funciones que el alta.
    """
    return recibo_service.previsualizar_cobro(db, body)


@router.get("/a-cobrar")
def a_cobrar(
    cliente_id: int = Query(...),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Qué tiene este cliente para cobrar: facturas con saldo y notas de crédito.

    El saldo de cada factura YA viene con las NC vinculadas restadas, así que
    una factura de 1.000 con una NC de 300 aparece con saldo 700. Todos los
    totales los calcula el backend con SUM.
    """
    from app.services import factura_service

    return factura_service.documentos_a_cobrar(db, cliente_id)


@router.put("/{recibo_id}/pagos", response_model=ReciboOut)
def guardar_pagos(
    recibo_id: int,
    pagos: list[PagoIn],
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    """Reemplaza la lista de pagos del recibo.

    El contador arma la lista en la pantalla (agrega, saca, cambia el banco) y
    manda la completa. Por eso se reemplaza entera y no se agrega de a una.
    """
    return recibo_service.guardar_pagos(db, recibo_id, pagos)


@router.post("/{recibo_id}/asiento")
def generar_asiento(
    recibo_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    """Genera el asiento de cobranza del recibo.

    El Debe sale de los PAGOS: uno por forma de pago, con su cuenta. El Haber
    es uno solo a `1.1.03.02 Documentos a cobrar`, con el cliente como auxiliar
    (por eso el estado de cuenta del cliente se actualiza solo).

    Si el recibo no tiene pagos, usa `cuenta_cobro_id` como antes: los recibos
    viejos no tienen tabla de pagos y no se rompen.
    """
    from app.services import asiento_automatico

    return asiento_automatico.asiento_de_cobranza(db, recibo_id)


@router.post("/{recibo_id}/asiento/anular")
def anular_asiento(
    recibo_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    """Anula el asiento del recibo. El recibo sigue como estaba."""
    from app.services import asiento_service, recibo_service as rs

    recibo = rs.obtener(db, recibo_id)
    if recibo.id_asiento is None:
        from app.core.errors import Rechazo

        raise Rechazo("El recibo no tiene asiento", 409)
    asiento_service.anular(db, recibo.id_asiento)
    return {"ok": True, "anulado": recibo_id}


@router.get("", response_model=list[ReciboOut])
def listar(
    cliente_id: int | None = Query(default=None),
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    sin_asiento: bool = Query(
        default=False, description="Solo los que todavía no están en los libros"
    ),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return recibo_service.listar(
        db,
        cliente_id=cliente_id,
        desde=desde,
        hasta=hasta,
        sin_asiento=sin_asiento,
    )


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
    sin_asiento: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Suma de los importes filtrados — la hace SQL, nunca el navegador.

    Acepta los mismos filtros que el listado, incluido `sin_asiento`: si no, el
    total de abajo mostraría la suma de otra cosa.
    """
    return {
        "total": recibo_service.total(
            db,
            cliente_id=cliente_id,
            desde=desde,
            hasta=hasta,
            sin_asiento=sin_asiento,
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


@router.post("/{recibo_id}/anular", response_model=ReciboOut)
def anular(
    recibo_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    return recibo_service.anular(db, recibo_id)


@router.post("/{recibo_id}/reabrir", response_model=ReciboOut)
def reabrir(
    recibo_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    return recibo_service.reabrir(db, recibo_id)


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
