from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Body, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_role
from app.core.errors import Rechazo
from app.database import get_db
from app.models.asiento import Asiento
from app.models.comprobante_interno import CODIGOS_COMPROBANTE
from app.models.usuario import Usuario
from app.schemas.asiento import (
    AsientoCrear,
    AsientoDetalleIn,
    AsientoOut,
    BusquedaCuentaOut,
    ComprobanteInternoCrear,
    ComprobanteInternoOut,
    ControlGeneralOut,
    SaldoOut,
)
from app.services import asiento_service, plan_cuenta_service

router = APIRouter(tags=["contabilidad"])

# El serializador vive en el service porque el router de facturas lo usa también
# (para los botones Generar / Modificar / Anular del asiento de una factura).
_asiento_a_json = asiento_service.a_json


# ============================================================ comprobantes

@router.get("/comprobantes-internos", response_model=list[ComprobanteInternoOut])
def listar_comprobantes(
    codigo: str = Query(default=""),
    anio: int | None = Query(default=None),
    estado: str = Query(default=""),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    filas = asiento_service.listar_comprobantes(
        db, codigo=codigo, anio=anio, estado=estado
    )
    return [
        {
            "id_comprobante": c.id_comprobante,
            "codigo_comprobante": c.codigo_comprobante,
            "anio": c.anio,
            "numero": c.numero,
            "id_ejercicio": c.id_ejercicio,
            "fecha": c.fecha,
            "concepto": c.concepto,
            "estado": c.estado,
            "numero_completo": c.numero_completo,
        }
        for c in filas
    ]


@router.get("/comprobantes-internos/codigos")
def codigos_disponibles(
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Los códigos internos dados de alta, para armar los menús de la pantalla."""
    from sqlalchemy import text

    return [
        {"codigo": r[0], "nombre": r[1], "origen": r[2]}
        for r in db.execute(
            text(
                "SELECT codigo, nombre, origen FROM config_comprobantes "
                "WHERE activa = 1 ORDER BY codigo"
            )
        )
    ]


@router.post(
    "/comprobantes-internos",
    response_model=ComprobanteInternoOut,
    status_code=status.HTTP_201_CREATED,
)
def crear_comprobante(
    body: ComprobanteInternoCrear,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    """Numera solo: el número es correlativo por código y por año."""
    c = asiento_service.crear_comprobante(
        db, body.codigo_comprobante, body.fecha, body.concepto
    )
    return {
        "id_comprobante": c.id_comprobante,
        "codigo_comprobante": c.codigo_comprobante,
        "anio": c.anio,
        "numero": c.numero,
        "id_ejercicio": c.id_ejercicio,
        "fecha": c.fecha,
        "concepto": c.concepto,
        "estado": c.estado,
        "numero_completo": c.numero_completo,
    }


# ================================================================ asientos

@router.get("/asientos")
def listar_asientos(
    codigo: str = Query(default="", description="FV, RC, AB, OP… vacío = todos"),
    origen: str = Query(
        default="", description="FACTURA, RECIBO o MANUAL. Vacío = todos"
    ),
    estado: str = Query(default="", description="Vacío = todo menos borradores"),
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Los asientos del período, agrupados por día con sus totales.

    Es lo que pinta la pantalla de Asientos: se elige el módulo y el día, y abajo
    salen los asientos de esa fecha con el Debe y el Haber de cada uno.

    El **módulo** (`origen`) es una pregunta distinta del **código**: "mostrame
    los recibos" incluye los asientos de cobranza (RC), y "mostrame las
    facturas" incluye los tres (FV, NC y ND). El contador piensa en módulos, no
    en códigos.
    """
    return asiento_service.listar(
        db, codigo=codigo, origen=origen, estado=estado, desde=desde, hasta=hasta
    )


@router.get("/asientos/{asiento_id}", response_model=AsientoOut)
def obtener_asiento(
    asiento_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    a = db.get(Asiento, asiento_id)
    if a is None:
        from app.core.errors import Rechazo

        raise Rechazo("El asiento no existe", 404)
    # Con `db`: las líneas traen `auxiliar_nombre` (de qué cliente es cada
    # movimiento). En el listado NO se pasa, porque ahí son cientos de asientos
    # y sería una consulta por línea.
    return _asiento_a_json(a, db)


@router.post(
    "/asientos", response_model=AsientoOut, status_code=status.HTTP_201_CREATED
)
def crear_asiento(
    body: AsientoCrear,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    """Asiento manual. Si no se pasa comprobante, se crea uno con el código
    que viene en el body (AB por defecto) y queda numerado solo."""
    from sqlalchemy import text

    id_comprobante = body.id_comprobante
    if id_comprobante is None:
        codigo = (body.codigo_comprobante or "AB").strip().upper()
        validos = asiento_service.codigos_validos(db)
        if codigo not in validos:
            raise Rechazo(
                f"Código de comprobante desconocido: «{codigo}». "
                f"Valores: {', '.join(validos)}.",
                400,
            )
        comp = asiento_service.crear_comprobante(
            db, codigo, body.fecha, body.concepto
        )
        id_comprobante = comp.id_comprobante

    a = asiento_service.crear_asiento(
        db, body.fecha, body.concepto, id_comprobante
    )
    return _asiento_a_json(a)


@router.put("/asientos/{asiento_id}")
def guardar_asiento(
    asiento_id: int,
    body: AsientoDetalleIn,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    """Reemplaza las líneas y deja el asiento CONTABILIZADO, todo de una.

    Es el botón "Guardar" de la pantalla: no hay un paso intermedio de
    "contabilizar" que el contador se pueda olvidar. Si el Debe no cierra con
    el Haber, se rechaza y el asiento queda en BORRADOR con las líneas nuevas,
    que se pueden corregir sin volver a tipearlas.
    """
    asiento = db.get(Asiento, asiento_id)
    if asiento is None:
        raise Rechazo("El asiento no existe", 404)
    if asiento.estado == "ANULADO":
        raise Rechazo(
            "El asiento está anulado: anulado es terminal, no se modifica más.",
            409,
        )
    if asiento.estado == "CONTABILIZADO":
        asiento_service.pasar_a_borrador(db, asiento_id)

    filas = [d.model_dump() for d in body.detalle]
    asiento_service.guardar_detalle(db, asiento_id, filas)
    asiento_service.contabilizar(db, asiento_id)
    return _asiento_a_json(db.get(Asiento, asiento_id))


@router.get("/plan-cuentas/buscar", response_model=list[BusquedaCuentaOut])
def buscar_cuentas(
    q: str = Query(default="", description="Código o nombre, parcial"),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Buscador de cuentas para armar las líneas del asiento.

    Solo devuelve las **imputables**: una agrupadora no recibe movimientos.
    """
    return plan_cuenta_service.buscar_imputables(db, q)


@router.put("/asientos/{asiento_id}/detalle")
def guardar_detalle(
    asiento_id: int,
    body: AsientoDetalleIn,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    """Reemplaza las líneas y recalcula los totales del asiento."""
    filas = [d.model_dump() for d in body.detalle]
    return asiento_service.guardar_detalle(db, asiento_id, filas)


@router.post("/asientos/{asiento_id}/contabilizar", response_model=AsientoOut)
def contabilizar(
    asiento_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    """De BORRADOR a CONTABILIZADO. Si el Debe no cierra con el Haber, no pasa."""
    asiento_service.contabilizar(db, asiento_id)
    return _asiento_a_json(db.get(Asiento, asiento_id), db)


@router.post("/asientos/{asiento_id}/borrador", response_model=AsientoOut)
def a_borrador(
    asiento_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    asiento_service.pasar_a_borrador(db, asiento_id)
    return _asiento_a_json(db.get(Asiento, asiento_id), db)


@router.post("/asientos/{asiento_id}/anular", response_model=AsientoOut)
def anular(
    asiento_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    asiento_service.anular(db, asiento_id)
    return _asiento_a_json(db.get(Asiento, asiento_id), db)


# ================================================================== saldos

@router.get("/mayores/{id_cuenta}")
def mayor_general(
    id_cuenta: int,
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    auxiliar_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """El mayor de UNA cuenta: sus movimientos con el saldo acumulado.

    Es el libro que muestra de dónde salió cada peso y a dónde fue. El saldo
    acumulado va en cada línea, así se puede ir siguiendo la cuenta.

    Para las cuentas con auxiliar (Documentos a cobrar, Clientes, bancos):
      - cada línea trae el **nombre** del cliente, no solo su id;
      - `auxiliares` trae un subtotal por cliente, que es el número que
        realmente interesa (el acumulado de la cuenta mezcla clientes);
      - con `auxiliar_id` se ve el mayor de UN cliente, y ahí el acumulado sí
        es el saldo de ese cliente.
    """
    return asiento_service.mayor(
        db, id_cuenta, desde=desde, hasta=hasta, auxiliar_id=auxiliar_id
    )


@router.get("/saldos", response_model=list[SaldoOut])
def saldos(
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    con_movimientos: bool = Query(
        default=False, description="Solo las cuentas que tienen movimientos"
    ),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Saldos por cuenta. Se calculan por SQL: no hay ningún saldo guardado.

    Por defecto trae **todas** las cuentas imputables, aunque estén en cero.
    El saldo sale con el signo de la naturaleza: en una deudora es
    Debe − Haber, en una acreedora es Haber − Debe.
    """
    return asiento_service.saldos(
        db, desde=desde, hasta=hasta, con_movimientos=con_movimientos
    )


@router.get("/control-general", response_model=ControlGeneralOut)
def control_general(
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Que TODO asiento contabilizado tenga Debe = Haber."""
    return asiento_service.control_general(db)