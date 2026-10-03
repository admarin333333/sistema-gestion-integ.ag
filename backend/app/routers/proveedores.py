from datetime import date

from fastapi import APIRouter, Body, Depends, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_role
from app.database import get_db
from app.models.proveedor import Proveedor
from app.models.usuario import Usuario
from app.schemas.cliente import ClienteListadoOut
from app.schemas.persona import PersonaCreate, PersonaUpdate
from app.services import clave_fiscal_service, proveedor_service

router = APIRouter(prefix="/proveedores", tags=["proveedores"])


def _armar(fila: Proveedor) -> dict:
    """Une la fila de `proveedores` con los datos de su persona."""
    p = fila.persona
    datos = {
        "id": fila.id,
        "persona_id": p.id,
        "tipo": "proveedor",
        "nro_cuenta": fila.nro_cuenta,
        "nombre_completo": p.nombre_completo,
        "fecha_alta": p.fecha_alta,
        "creado": p.creado,
        "actualizado": p.actualizado,
        "servicios": [],
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
    personas = proveedor_service.listar(db, q, desde, hasta, orden, desc)
    return [_armar(p.proveedor) for p in personas if p.proveedor]


@router.post("", response_model=ClienteListadoOut, status_code=status.HTTP_201_CREATED)
def crear(
    body: PersonaCreate = Body(...),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    persona = proveedor_service.crear(db, body, usuario=user.usuario)
    db.refresh(persona)
    return _armar(persona.proveedor)


@router.get("/{proveedor_id}", response_model=ClienteListadoOut)
def obtener(
    proveedor_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    proveedor_service.obtener(db, proveedor_id)
    return _armar(db.get(Proveedor, proveedor_id))


@router.put("/{proveedor_id}", response_model=ClienteListadoOut)
def actualizar(
    proveedor_id: int,
    body: PersonaUpdate = Body(...),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    # Ojo: `body` ya viene tipado por FastAPI. No hay que re-armarlo con
    # `PersonaUpdate(**dict(body))`, porque eso marca como "enviados" todos los
    # campos (incluidos los que vieram con None) y el service los pisaría.
    persona = proveedor_service.actualizar(
        db, proveedor_id, body, usuario=user.usuario
    )
    db.refresh(persona)
    return _armar(persona.proveedor)


@router.get("/{proveedor_id}/clave-fiscal/historial")
def historial_clave_fiscal(
    proveedor_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Cada cambio de clave fiscal del proveedor (del más nuevo al más viejo)."""
    persona = proveedor_service.obtener(db, proveedor_id)
    return clave_fiscal_service.historial(db, persona.id)


@router.delete("/{proveedor_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(
    proveedor_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    proveedor_service.eliminar(db, proveedor_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
