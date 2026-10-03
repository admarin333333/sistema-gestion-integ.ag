from datetime import datetime

from sqlalchemy import func, inspect, or_, text
from sqlalchemy.orm import Session

from app.core.errors import Rechazo
from app.models.alicuota import AlicuotaIva
from app.models.cliente import Cliente
from app.models.persona import Persona
from app.models.servicio import Servicio
from app.schemas.persona import PersonaCreate, PersonaUpdate
from app.services import clave_fiscal_service

# Tablas que cuentan como movimiento del cliente, con su condición extra.
TABLAS_DE_MOVIMIENTO = (
    ("facturas", ""),
    ("recibos", ""),
    ("anticipos", "AND estado != 'eliminado'"),
)

# Marca para saber si el cliente mandó la clave fiscal o no la tocó.
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
    """Busca por apellido y nombre o razón social (y CUIT/DNI), en cualquier
    orden: cada palabra escrita debe aparecer en algún campo."""
    consulta = db.query(Persona).join(Cliente, Cliente.persona_id == Persona.id)
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


# Los órdenes que el contador puede pedir, y la columna por la que se hace.
#
# El `ORDER BY` va SIEMPRE en SQL, nunca en el navegador: con 5.000 clientes el
# frontend tendría que traerlos todos para recién ahí compararlos, y el contador
# esperaría la pantalla. Además el listado del Excel sale del backend, y si acá
# se ordenara distinto el papel y la pantalla no coincidirían.
ORDENES = {
    # Por defecto: apellido, y si no hay apellido el nombre (que en una persona
    # jurídica es la razón social).
    "nombre": (func.coalesce(Persona.apellido, Persona.nombre), Persona.nombre),
    "apellido": (Persona.apellido, Persona.nombre),
    "razon_social": (Persona.nombre, Persona.apellido),
    "fecha_alta": (Persona.fecha_alta, Persona.nombre),
    "cuit": (func.coalesce(Persona.cuit, ""), Persona.nombre),
    "nro_cuenta": (Cliente.nro_cuenta, Persona.nombre),
    "localidad": (func.coalesce(Persona.localidad, ""), Persona.nombre),
}


def _aplicar_orden(consulta, orden: str | None, desc: bool = False):
    """Arma el `ORDER BY` a pedido.

    `orden` viene del usuario: se busca en el diccionario y, si no está, se usa
    el de por defecto. Nunca se pasa a `text()` sin comprobar — eso sería un
    hole de inyección. Un orden desconocido no es un error: es el de siempre.

    `desc` invierte: el contador quiere "de la Z a la A" y no hace falta tener
    dos juegos de columnas.
    """
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
    consulta = db.query(Persona).join(Cliente, Cliente.persona_id == Persona.id)
    consulta = _filtrar_fecha(consulta, desde, hasta)
    return _aplicar_orden(consulta, orden, desc).all()


def obtener(db: Session, cliente_id: int) -> Persona:
    cliente = db.get(Cliente, cliente_id)
    if cliente is None:
        raise Rechazo("No existe ese cliente", 404)
    return cliente.persona


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
    """Siguiente número de cuenta para clientes."""
    ultimo = db.query(func.max(Cliente.nro_cuenta)).scalar()
    return int(ultimo or 0) + 1


def _servicios_de(db: Session, ids: list[int]) -> list[Servicio]:
    if not ids:
        return []
    encontrados = db.query(Servicio).filter(Servicio.id.in_(ids)).all()
    if len(encontrados) != len(set(ids)):
        raise Rechazo("Elegiste un servicio que no existe")
    return encontrados


def crear(
    db: Session,
    datos: PersonaCreate,
    servicios: list[int],
    usuario: str | None = None,
) -> Persona:
    _verificar_unicos(db, datos.cuit, datos.dni)
    _verificar_alicuota(db, datos.alicuota_iva_id)
    campos = datos.model_dump()
    clave = campos.pop("clave_fiscal", None)
    persona = Persona(**campos)
    # La clave fiscal deja sus fechas solas (primera carga).
    clave_fiscal_service.aplicar(persona, clave, usuario)
    db.add(persona)
    db.flush()  # obtener persona.id sin commit
    cliente = Cliente(persona_id=persona.id, nro_cuenta=_proximo_nro_cuenta(db))
    db.add(cliente)
    # Ojo: la relación `servicios` es de **Cliente**, no de Persona. Si se
    # asigna `persona.servicios` se crea un atributo suelto en el aire y los
    # servicios nunca se guardan (por eso el alta los perdía).
    cliente.servicios = _servicios_de(db, servicios)
    if clave:
        clave_fiscal_service.registrar_cambio(db, persona, None, clave_fiscal_service.normalizar(clave), usuario)
    db.commit()
    db.refresh(persona)
    return persona


def actualizar(
    db: Session,
    cliente_id: int,
    datos: PersonaUpdate,
    servicios: list[int],
    usuario: str | None = None,
) -> Persona:
    cliente = db.get(Cliente, cliente_id)
    if cliente is None:
        raise Rechazo("No existe ese cliente", 404)
    persona = cliente.persona
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
            db, persona, anterior, clave_fiscal_service.normalizar(persona.clave_fiscal), usuario
        )
    cliente.servicios = _servicios_de(db, servicios)
    persona.actualizado = datetime.utcnow()
    db.commit()
    db.refresh(persona)
    return persona


def tiene_movimientos(db: Session, cliente_id: int) -> bool:
    """¿El cliente tiene facturas, recibos o anticipos vigentes?"""
    inspector = inspect(db.get_bind())
    for tabla, condicion in TABLAS_DE_MOVIMIENTO:
        if not inspector.has_table(tabla):
            continue
        cantidad = db.execute(
            text(f"SELECT COUNT(*) FROM {tabla} WHERE cliente_id = :id {condicion}"),
            {"id": cliente_id},
        ).scalar()
        if cantidad:
            return True
    return False


def eliminar(db: Session, cliente_id: int) -> None:
    cliente = db.get(Cliente, cliente_id)
    if cliente is None:
        raise Rechazo("No existe ese cliente", 404)
    if tiene_movimientos(db, cliente_id):
        raise Rechazo(
            "No se puede eliminar: el cliente ya tiene facturas, recibos "
            "o anticipos. Anulá esos movimientos o dejalo en archivo.",
            409,
        )
    # Los anticipos eliminados no son movimiento: se van con el cliente
    if inspect(db.get_bind()).has_table("anticipos"):
        db.execute(
            text("DELETE FROM anticipos WHERE cliente_id = :id AND estado = 'eliminado'"),
            {"id": cliente_id},
        )
    persona = cliente.persona
    db.delete(cliente)
    db.delete(persona)
    db.commit()