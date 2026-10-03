from datetime import datetime

from sqlalchemy import func, inspect, or_, text
from sqlalchemy.orm import Session

from app.core.errors import Rechazo
from app.models.alicuota import AlicuotaIva
from app.models.persona import Persona
from app.models.proveedor import Proveedor
from app.schemas.persona import PersonaCreate, PersonaUpdate
from app.services import clave_fiscal_service

# Marca para saber si el proveedor mandó la clave fiscal o no la tocó.
_SIN_CAMINO = object()


def _filtrar_fecha(consulta, desde, hasta):
    if desde:
        consulta = consulta.filter(Persona.fecha_alta >= desde)
    if hasta:
        consulta = consulta.filter(Persona.fecha_alta <= hasta)
    return consulta


def _buscar(
    db: Session,
    termino: str,
    desde=None,
    hasta=None,
    orden: str | None = None,
    desc: bool = False,
) -> list[Persona]:
    """Busca proveedores por apellido/nombre/razón social + CUIT/DNI."""
    consulta = db.query(Persona).join(Proveedor, Proveedor.persona_id == Persona.id)
    for palabra in termino.strip().split():
        texto = f"%{palabra}%"
        digitos = f"%{_solo_digitos(palabra)}%"
        consulta = consulta.filter(
            or_(
                Persona.nombre.like(texto),
                Persona.apellido.like(texto),
                func.replace(func.coalesce(Persona.cuit, ""), "-", "").like(digitos),
                func.coalesce(Persona.dni, "").like(digitos),
            )
        )
    consulta = _filtrar_fecha(consulta, desde, hasta)
    return _aplicar_orden(consulta, orden, desc).all()


def _solo_digitos(valor: str) -> str:
    return valor.replace("-", "").replace(".", "").replace(" ", "")


# Los mismos órdenes que en `cliente_service.ORDENES`, pero sobre la tabla
# `proveedores`. Se repiten las claves a propósito: son dos listados distintos
# y que cada uno se lea solo vale más que un `if es_proveedor` por columna.
ORDENES = {
    "nombre": (func.coalesce(Persona.apellido, Persona.nombre), Persona.nombre),
    "apellido": (Persona.apellido, Persona.nombre),
    "razon_social": (Persona.nombre, Persona.apellido),
    "fecha_alta": (Persona.fecha_alta, Persona.nombre),
    "cuit": (func.coalesce(Persona.cuit, ""), Persona.nombre),
    "nro_cuenta": (Proveedor.nro_cuenta, Persona.nombre),
    "localidad": (func.coalesce(Persona.localidad, ""), Persona.nombre),
}


def _aplicar_orden(consulta, orden: str | None, desc: bool = False):
    """Arma el `ORDER BY` a pedido. Ver la nota en `cliente_service`."""
    columnas = ORDENES.get((orden or "").lower(), ORDENES["nombre"])
    if desc:
        columnas = [c.desc() for c in columnas]
    return consulta.order_by(*columnas)


def listar(
    db: Session,
    termino: str | None = None,
    desde=None,
    hasta=None,
    orden: str | None = None,
    desc: bool = False,
) -> list[Persona]:
    if termino and termino.strip():
        return _buscar(db, termino, desde, hasta, orden, desc)
    consulta = db.query(Persona).join(Proveedor, Proveedor.persona_id == Persona.id)
    consulta = _filtrar_fecha(consulta, desde, hasta)
    return _aplicar_orden(consulta, orden, desc).all()


def obtener(db: Session, proveedor_id: int) -> Persona:
    proveedor = db.get(Proveedor, proveedor_id)
    if proveedor is None:
        raise Rechazo("No existe ese proveedor", 404)
    return proveedor.persona


def _verificar_unicos(
    db: Session,
    cuit: str | None,
    dni: str | None,
    excluye: int | None = None,
):
    """CUIT/DNI únicos globalmente en personas."""
    if cuit:
        consulta = db.query(Persona).filter(Persona.cuit == cuit)
        if excluye:
            consulta = consulta.filter(Persona.id != excluye)
        if consulta.first():
            raise Rechazo("Ya existe una persona con ese CUIT", 409)
    if dni:
        consulta = db.query(Persona).filter(Persona.dni == dni)
        if excluye:
            consulta = consulta.filter(Persona.id != excluye)
        if consulta.first():
            raise Rechazo("Ya existe una persona con ese DNI", 409)


def _verificar_alicuota(db: Session, alicuota_iva_id: int | None) -> None:
    if alicuota_iva_id is None:
        return
    alicuota = db.get(AlicuotaIva, alicuota_iva_id)
    if alicuota is None or not alicuota.activo:
        raise Rechazo("Elegí una alícuota de IVA válida", 409)


def _proximo_nro_cuenta(db: Session) -> int:
    """Siguiente número de cuenta para proveedores."""
    ultimo = db.query(func.max(Proveedor.nro_cuenta)).scalar()
    return int(ultimo or 0) + 1


def crear(
    db: Session, datos: PersonaCreate, usuario: str | None = None
) -> Persona:
    _verificar_unicos(db, datos.cuit, datos.dni)
    _verificar_alicuota(db, datos.alicuota_iva_id)
    campos = datos.model_dump()
    clave = campos.pop("clave_fiscal", None)
    persona = Persona(**campos)
    clave_fiscal_service.aplicar(persona, clave, usuario)
    db.add(persona)
    db.flush()
    proveedor = Proveedor(persona_id=persona.id, nro_cuenta=_proximo_nro_cuenta(db))
    db.add(proveedor)
    if clave:
        clave_fiscal_service.registrar_cambio(
            db, persona, None, clave_fiscal_service.normalizar(clave), usuario
        )
    db.commit()
    db.refresh(persona)
    return persona


def actualizar(
    db: Session,
    proveedor_id: int,
    datos: PersonaUpdate,
    usuario: str | None = None,
) -> Persona:
    proveedor = db.get(Proveedor, proveedor_id)
    if proveedor is None:
        raise Rechazo("No existe ese proveedor", 404)
    persona = proveedor.persona
    _verificar_unicos(db, datos.cuit, datos.dni, excluye=persona.id)
    _verificar_alicuota(db, datos.alicuota_iva_id)
    campos = datos.model_dump(exclude_unset=True)
    clave = campos.pop("clave_fiscal", _SIN_CAMINO)
    anterior = clave_fiscal_service.normalizar(persona.clave_fiscal)
    for campo, valor in campos.items():
        setattr(persona, campo, valor)
    if clave is not _SIN_CAMINO:
        clave_fiscal_service.aplicar(persona, clave, usuario)
        clave_fiscal_service.registrar_cambio(
            db,
            persona,
            anterior,
            clave_fiscal_service.normalizar(persona.clave_fiscal),
            usuario,
        )
    persona.actualizado = datetime.utcnow()
    db.commit()
    db.refresh(persona)
    return persona


def tiene_movimientos(db: Session, proveedor_id: int) -> bool:
    """¿El proveedor tiene compras vigentes?"""
    inspector = inspect(db.get_bind())
    if not inspector.has_table("compras"):
        return False
    cantidad = db.execute(
        text("SELECT COUNT(*) FROM compras WHERE proveedor_id = :id AND estado != 'anulada'"),
        {"id": proveedor_id},
    ).scalar()
    return bool(cantidad)


def eliminar(db: Session, proveedor_id: int) -> None:
    proveedor = db.get(Proveedor, proveedor_id)
    if proveedor is None:
        raise Rechazo("No existe ese proveedor", 404)
    if tiene_movimientos(db, proveedor_id):
        raise Rechazo(
            "No se puede eliminar: el proveedor ya tiene compras. "
            "Anulá esos movimientos o dejalo en archivo.",
            409,
        )
    persona = proveedor.persona
    db.delete(proveedor)
    db.delete(persona)
    db.commit()