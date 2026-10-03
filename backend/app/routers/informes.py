from datetime import date
from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.usuario import Usuario
from app.services import informes_service

router = APIRouter(prefix="/informes", tags=["informes"])

# Los días de plazo con los que se vence una factura. Es el mismo número que
# usa la pantalla al calcular el vencimiento solo (ver `FacturaForm.jsx`).
#
# Va en un solo lugar del backend y la pantalla lo recibe en la respuesta del
# informe (`dias_plazo`), para que el número que se ve en el informe y el que se
# calculó al cargar la factura sean el mismo. Si uno cambia y el otro no, el
# contador ve una factura vencida con un plazo que no coincide.
DIAS_PLAZO = informes_service.DIAS_PLAZO

_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/estado-deuda")
def estado_deuda(
    cliente_id: int | None = Query(default=None),
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    solo_vencidas: bool = Query(default=False),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Estado de deuda total: facturas, notas de crédito, notas de débito pendientes.

    Trae dos cosas: lo que está pendiente de pago y **lo que ya venció** (con
    cuántos días). Son las dos preguntas del día y van juntas: el contador no
    quiere "cuánto me deben" separado de "cuánto de eso lo tengo que ir a
    cobrar ya".

    `solo_vencidas` acota la lista a lo vencido, para el que solo quiere ir a
    buscar a los que atrasaron.
    """
    data = informes_service.informe_estado_deuda(
        db, desde=desde, hasta=hasta, cliente_id=cliente_id
    )
    if solo_vencidas:
        vencidas = [i for i in data["items"] if i["vencido"]]
        data["items"] = vencidas
        data["cantidad_total"] = len(vencidas)
        data["pendiente_general"] = sum(i["pendiente"] for i in vencidas)
    data["solo_vencidas"] = solo_vencidas
    return data


@router.get("/estado-deuda/export.xlsx")
def exportar_estado_deuda(
    cliente_id: int | None = Query(default=None),
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    solo_vencidas: bool = Query(default=False),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Estado de deuda en Excel."""
    data = informes_service.informe_estado_deuda(db, desde=desde, hasta=hasta, cliente_id=cliente_id)
    if solo_vencidas:
        vencidas = [i for i in data["items"] if i["vencido"]]
        data["items"] = vencidas
        data["cantidad_total"] = len(vencidas)
        data["pendiente_general"] = sum(i["pendiente"] for i in vencidas)
    contenido = informes_service.estado_deuda_excel(data)
    nombre = f"estado_deuda_{date.today().isoformat()}.xlsx"
    return Response(
        content=contenido,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


@router.get("/cuenta-corriente")
def cuenta_corriente(
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    solo_vencidos: bool = Query(default=False),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """La cuenta corriente de TODOS los clientes: las partidas abiertas agrupadas.

    A diferencia del estado de deuda (que es el detalle de un cliente), esto es
    **la lista de a quién llamar**: cuánto debe cada uno, cuánto está vencido y
    su teléfono.
    """
    return informes_service.informe_cuenta_corriente(
        db, desde=desde, hasta=hasta, solo_vencidos=solo_vencidos
    )


@router.get("/cuenta-corriente/export.xlsx")
def exportar_cuenta_corriente(
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    solo_vencidos: bool = Query(default=False),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """La cuenta corriente de todos los clientes en Excel."""
    data = informes_service.informe_cuenta_corriente(
        db, desde=desde, hasta=hasta, solo_vencidos=solo_vencidos
    )
    contenido = informes_service.cuenta_corriente_excel(data)
    nombre = f"cuenta_corriente_{date.today().isoformat()}.xlsx"
    return Response(
        content=contenido,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


@router.get("/libro-iva-ventas")
def libro_iva_ventas(
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    incluir_anuladas: bool = Query(default=False),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Libro de IVA Ventas: una línea por comprobante, en orden correlativo y por día.

    Sale de `facturas`, no de los asientos: el libro registra los documentos
    emitidos, Contabilizado o no. Una factura guardada sin asentar igual emitió
    comprobante y su IVA hay que pagarlo.
    """
    return informes_service.libro_iva_ventas(
        db, desde=desde, hasta=hasta, incluir_anuladas=incluir_anuladas
    )


@router.get("/libro-iva-ventas/export.xlsx")
def exportar_libro_iva_ventas(
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    incluir_anuladas: bool = Query(default=False),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """El Libro de IVA Ventas en Excel."""
    data = informes_service.libro_iva_ventas(
        db, desde=desde, hasta=hasta, incluir_anuladas=incluir_anuladas
    )
    contenido = informes_service.libro_iva_ventas_excel(data)
    nombre = f"libro_iva_ventas_{date.today().isoformat()}.xlsx"
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


@router.get("/proveedores")
def proveedores(
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Listado de proveedores con alta en el período."""
    return informes_service.informe_proveedores(db, desde=desde, hasta=hasta)


@router.get("/proveedores/export.xlsx")
def exportar_proveedores(
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Listado de proveedores en Excel."""
    data = informes_service.informe_proveedores(db, desde=desde, hasta=hasta)
    contenido = informes_service.proveedores_excel(data)
    nombre = f"proveedores_{date.today().isoformat()}.xlsx"
    return Response(
        content=contenido,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


@router.get("/centros-costos")
def centros_costos(
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Informe por centro de costos, con los importes tomados de los asientos."""
    return informes_service.informe_centros(db, desde=desde, hasta=hasta)


@router.get("/centros-cuentas")
def centros_cuentas(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Los centros de costos y sus cuentas de gasto, SIN importes.

    Es la rama de GASTOS del plan de cuentas (6.1 administración, 6.2
    comercialización, 6.3 financieros, 6.4 otros) con las cuentas imputables de
    cada una. La usan las pantallas para que el contador elija en qué cuenta se
    asienta un gasto, sin tener que saber los códigos de memoria.
    """
    return informes_service.centros_de_costos(db)


@router.get("/centros-costos/export.xlsx")
def exportar_centros_costos(
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Informe por centro de costos en Excel."""
    data = informes_service.informe_centros(db, desde=desde, hasta=hasta)
    contenido = informes_service.centros_excel(data)
    nombre = f"centros_costos_{date.today().isoformat()}.xlsx"
    return Response(
        content=contenido,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


@router.get("/resultados")
def resultados(
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Informe de resultados: ingresos - gastos = neto, más tabla de bienes."""
    return informes_service.informe_resultados(db, desde=desde, hasta=hasta)


@router.get("/resultados/export.xlsx")
def exportar_resultados(
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Informe de resultados en Excel."""
    data = informes_service.informe_resultados(db, desde=desde, hasta=hasta)
    contenido = informes_service.resultados_excel(data)
    nombre = f"informe_resultados_{date.today().isoformat()}.xlsx"
    return Response(
        content=contenido,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


@router.get("/claves-fiscales")
def claves_fiscales(
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    terminacion: int | None = Query(default=None, ge=0, le=9),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Informe de CUIT y clave fiscal de ARCA de todos los clientes.

    `desde`/`hasta` filtran por la fecha en que se cargó la clave fiscal.
    """
    return informes_service.informe_claves_fiscales(
        db, desde=desde, hasta=hasta, terminacion=terminacion
    )


@router.get("/claves-fiscales/export.xlsx")
def exportar_claves_fiscales(
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    terminacion: int | None = Query(default=None, ge=0, le=9),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Informe de CUIT y clave fiscal en Excel, agrupado por terminación."""
    data = informes_service.informe_claves_fiscales(
        db, desde=desde, hasta=hasta, terminacion=terminacion
    )
    contenido = informes_service.claves_fiscales_excel(data)
    nombre = f"claves_fiscales_{date.today().isoformat()}.xlsx"
    return Response(
        content=contenido,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )