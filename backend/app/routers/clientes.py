from datetime import date

from fastapi import APIRouter, Body, Depends, Query, status
from fastapi.responses import Response
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_role
from app.core.errors import datos_invalidos
from app.database import get_db
from app.models.cliente import Cliente
from app.models.proveedor import Proveedor
from app.models.usuario import Usuario
from app.schemas.cliente import ClienteListadoOut
from app.schemas.persona import (
    PersonaCreate,
    PersonaUpdate,
    cuit_advertencia,
)
from app.schemas.recibo import CuentaCorrienteOut
from app.schemas.sugerencia import SugerenciaCrear, SugerenciaOut
from app.services import (
    clave_fiscal_service,
    cliente_service,
    cuenta_service,
    sugerencia_service,
)

router = APIRouter(prefix="/clientes", tags=["clientes"])

_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _armar(fila_cliente: Cliente) -> dict:
    """Une la fila del módulo (clientes) con los datos de su persona."""
    p = fila_cliente.persona
    datos = {
        "id": fila_cliente.id,
        "persona_id": p.id,
        "tipo": "cliente",
        "nro_cuenta": fila_cliente.nro_cuenta,
        "nombre_completo": p.nombre_completo,
        "fecha_alta": p.fecha_alta,
        "creado": p.creado,
        "actualizado": p.actualizado,
        "servicios": [{"id": s.id, "nombre": s.nombre, "orden": s.orden} for s in fila_cliente.servicios],
        "sugerencias": [],
    }
    for campo in (
        "tipo_persona", "nombre", "apellido", "cuit", "dni", "email",
        "cod_area", "telefono", "calle", "numero_calle", "localidad",
        "codigo_postal", "provincia", "actividad_economica", "tipo_actividad",
        "condicion_iva", "alicuota_iva_id", "observaciones",
        "fecha_cierre_ejercicio", "presenta_eecc",
        # clave fiscal de ARCA (con sus fechas de carga y modificación)
        "clave_fiscal", "fecha_carga_clave_fiscal", "fecha_modif_clave_fiscal",
    ):
        datos[campo] = getattr(p, campo, None)
    datos["alicuota_iva"] = (
        {"id": p.alicuota_iva.id, "nombre": p.alicuota_iva.nombre, "porcentaje": p.alicuota_iva.porcentaje}
        if p.alicuota_iva
        else None
    )
    # Aviso del dígito verificador del CUIT (no bloquea, solo informa).
    datos["cuit_advertencia"] = cuit_advertencia(p.cuit)
    return datos


@router.get("", response_model=list[ClienteListadoOut])
def listar(
    q: str | None = Query(default=None, description="Busca por nombre, DNI o CUIT"),
    desde: date | None = Query(default=None, description="Alta desde"),
    hasta: date | None = Query(default=None, description="Alta hasta"),
    orden: str | None = Query(
        default=None,
        description=(
            "Columna por la que se ordena: nombre, apellido, razon_social, "
            "fecha_alta, cuit, nro_cuenta o localidad"
        ),
    ),
    desc: bool = Query(default=False, description="Invierte el orden"),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    personas = cliente_service.listar(db, q, desde, hasta, orden, desc)
    # Cada persona viene con su fila en `clientes` (búsqueda inversa).
    return [_armar(p.cliente) for p in personas if p.cliente]


@router.post("", response_model=ClienteListadoOut, status_code=status.HTTP_201_CREATED)
def crear(
    body: dict = Body(...),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    # El cuerpo trae los datos de la persona + `servicios` (lista de ids).
    datos = {k: v for k, v in body.items() if k != "servicios"}
    servicios = body.get("servicios") or []
    try:
        schema = PersonaCreate(**datos)
    except ValidationError as e:
        raise datos_invalidos(e) from e
    persona = cliente_service.crear(db, schema, servicios, usuario=user.usuario)
    db.refresh(persona)
    return _armar(persona.cliente)


@router.get("/{cliente_id}", response_model=ClienteListadoOut)
def obtener(
    cliente_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    cliente_service.obtener(db, cliente_id)
    return _armar(db.get(Cliente, cliente_id))


@router.put("/{cliente_id}", response_model=ClienteListadoOut)
def actualizar(
    cliente_id: int,
    body: dict = Body(...),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    datos = {k: v for k, v in body.items() if k != "servicios"}
    servicios = body.get("servicios") or []
    try:
        schema = PersonaUpdate(**datos)
    except ValidationError as e:
        raise datos_invalidos(e) from e
    persona = cliente_service.actualizar(
        db, cliente_id, schema, servicios, usuario=user.usuario
    )
    db.refresh(persona)
    return _armar(persona.cliente)


@router.get("/{cliente_id}/clave-fiscal/historial")
def historial_clave_fiscal(
    cliente_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Cada cambio de clave fiscal del cliente (del más nuevo al más viejo)."""
    persona = cliente_service.obtener(db, cliente_id)
    return clave_fiscal_service.historial(db, persona.id)


@router.delete("/{cliente_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(
    cliente_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    cliente_service.eliminar(db, cliente_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{cliente_id}/cuenta", response_model=CuentaCorrienteOut)
def cuenta_corriente(
    cliente_id: int,
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Historial de la cuenta corriente del cliente."""
    return cuenta_service.movimientos(db, cliente_id, desde=desde, hasta=hasta)


@router.get("/{cliente_id}/cuenta/export.xlsx")
def exportar_cuenta(
    cliente_id: int,
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Cuenta corriente del cliente en Excel."""
    datos = cuenta_service.movimientos(db, cliente_id, desde=desde, hasta=hasta)
    contenido = cuenta_service.informe_excel(
        cliente_service.obtener(db, cliente_id),
        datos.movimientos,
        datos.total_debe,
        datos.total_haber,
        datos.saldo,
        desde=desde,
        hasta=hasta,
    )
    nombre = f"cuenta_corriente_{cliente_id}_{date.today().isoformat()}.xlsx"
    return Response(
        content=contenido,
        media_type=_XLSX,
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


@router.get("/{cliente_id}/sugerencias", response_model=list[SugerenciaOut])
def sugerencias(
    cliente_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return sugerencia_service.listar(db, cliente_id)


@router.post("/{cliente_id}/sugerencias", response_model=SugerenciaOut)
def crear_sugerencia(
    cliente_id: int,
    body: SugerenciaCrear,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return sugerencia_service.crear(db, cliente_id, body)
