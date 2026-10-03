from datetime import date

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_role
from app.core.errors import Rechazo
from app.database import get_db
from app.models.asiento import Asiento
from app.models.usuario import Usuario
from app.schemas.asiento import AsientoDetalleIn
from app.schemas.factura import (
    EnvioMasivo,
    EnvioResultado,
    FacturaActualizar,
    FacturaCrear,
    FacturaOut,
    FacturaPreview,
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


# ==================================================== asiento de la factura
#
# Los tres botones son del ASIENTO, no de la factura. Se separan a propósito:
# el asiento contabilizado es un documento contable y el contador tiene que
# poder mirarlo, decidir y tocarlo por su cuenta.
#
# Anular la factura NO anula el asiento (ver factura_service.anular).


@router.post("/preview-asiento")
def preview_asiento(
    body: FacturaPreview,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Cómo **quedaría** el asiento de esta factura. NO guarda nada.

    Es lo que se muestra en la pantalla de alta para que el contador vea las
    cuentas y los importes antes de decidir. Recién al apretar "OK, facturar"
    se guarda la factura y el asiento, ya contabilizado.

    Si el IVA no está desglosado, avisa: el importe entero iría a ingresos.
    """
    from app.services import asiento_automatico, factura_service as fs

    if body.cliente_id is None:
        raise Rechazo("Elegí un cliente para ver el asiento", 400)
    if body.importe is None or body.importe <= 0:
        raise Rechazo("Cargá el importe antes de ver el asiento", 400)

    # Sin alícuota NO se desglosa: se pasa `importe` como neto y `iva` en cero
    # para que la proyección entre por la rama que avisa "no elegiste
    # alícuota". Si se desglosara acá, `neto` e `iva` vendrían sempre
    # calculados y el aviso nunca aparecería.
    if body.alicuota_iva_id is None:
        # Sin alícuota, `_desglosar_iva` devolvería (importe, 0). Eso es
        # correcto para guardar, pero acá el None tiene que sobrevivir: si se
        # pasara un 0, la proyección no avisaría que falta elegir la alícuota.
        neto, iva = None, None
    else:
        # El desglose sale del MISMO lugar que usa el alta real, así que el
        # preview y el asiento guardado no pueden diferir en un centavo.
        neto, iva, _aplicada = fs._desglosar_iva(
            db, float(body.importe), body.alicuota_iva_id
        )

    return asiento_automatico.proyectar_venta(
        db,
        fecha=body.fecha,
        tipo_comprobante=body.tipo_comprobante,
        punto_venta=body.punto_venta or "0000",
        numero=body.numero or "0",
        concepto=body.concepto,
        condicion_venta=body.condicion_venta,
        tipo_operacion=body.tipo_operacion or "SERVICIOS",
        importe=body.importe,
        neto=neto,
        iva=iva,
        cliente_id=body.cliente_id,
    )


@router.post("/{factura_id}/asiento")
def generar_asiento(
    factura_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    """Botón Generar. Sale a contabilizado, sin pasos intermedios."""
    from app.services import asiento_automatico, asiento_service

    factura = factura_service.obtener(db, factura_id)
    if factura.id_asiento is not None:
        raise Rechazo(
            f"La factura ya tiene el asiento {factura.numero_comprobante_asiento}. "
            "Si querés cambiarlo, anulá ese asiento y generá uno nuevo.",
            409,
        )
    resultado = asiento_automatico.asiento_de_venta(db, factura_id)
    # Se devuelve el asiento armado (fecha, cuentas, debe y haber de cada
    # línea, y los totales) para que la pantalla lo muestre sin ir a buscarlo.
    if resultado.get("asiento_id"):
        return {
            **resultado,
            "asiento": asiento_service.a_json(
                db.get(Asiento, resultado["asiento_id"]), db
            ),
        }
    return resultado


@router.put("/{factura_id}/asiento")
def modificar_asiento(
    factura_id: int,
    body: AsientoDetalleIn,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    """Botón Modificar: reemplaza las líneas del asiento de esta factura.

    Hace los tres pasos juntos — volver a borrador, guardar las líneas nuevas
    y contabilizar — porque si el contador las guarda y después no contabiliza,
    la factura queda con un asiento a medio hacer que no aparece en los saldos.

    Si el Debe no cierra con el Haber, `contabilizar` lo rechaza y avisa cuánto
    falta. El asiento queda en BORRADOR con las líneas que sejxaron, así no
    se pierde nada.
    """
    from app.services import asiento_service

    factura = factura_service.obtener(db, factura_id)
    if factura.id_asiento is None:
        raise Rechazo(
            "La factura no tiene asiento: primero apretá Generar", 409
        )
    asiento_id = factura.id_asiento

    asiento = db.get(Asiento, asiento_id)
    if asiento.estado == "ANULADO":
        raise Rechazo(
            "El asiento está ANULADO y no se modifica más: anulado es "
            "terminal. Generá uno nuevo.",
            409,
        )
    if asiento.estado == "CONTABILIZADO":
        asiento_service.pasar_a_borrador(db, asiento_id)

    filas = [d.model_dump() for d in body.detalle]
    asiento_service.guardar_detalle(db, asiento_id, filas)
    asiento_service.contabilizar(db, asiento_id)
    return asiento_service.a_json(db.get(Asiento, asiento_id), db)


@router.post("/{factura_id}/asiento/anular")
def anular_asiento(
    factura_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    """Botón Anular asiento. La factura sigue como estaba: son dos cosas
    separadas."""
    factura = factura_service.obtener(db, factura_id)
    if factura.id_asiento is None:
        raise Rechazo("La factura no tiene asiento", 409)
    from app.services import asiento_service

    asiento_service.anular(db, factura.id_asiento)
    return factura_service.obtener(db, factura_id)
