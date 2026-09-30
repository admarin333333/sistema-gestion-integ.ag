from datetime import datetime

from sqlalchemy import func, inspect, or_, text
from sqlalchemy.orm import Session

from app.core.errors import Rechazo
from app.models.cliente import Cliente
from app.models.servicio import Servicio
from app.schemas.cliente import ClienteActualizar, ClienteCrear

# Tablas que cuentan como movimiento del cliente, con su condición extra.
# Los anticipos ya ELIMINADOS no son movimiento vivo: no bloquean el borrado
# del cliente, pero sus filas se van junto con él.
TABLAS_DE_MOVIMIENTO = (
    ("facturas", ""),
    ("recibos", ""),
    ("anticipos", "AND estado != 'eliminado'"),
)


def _buscar(db: Session, termino: str) -> list[Cliente]:
    """Busca por nombre, apellido, CUIT o DNI — sin importar los guiones."""
    texto = f"%{termino.strip()}%"
    digitos = f"%{_solo_digitos(termino)}%"
    return (
        db.query(Cliente)
        .filter(
            or_(
                Cliente.nombre.like(texto),
                Cliente.apellido.like(texto),
                func.replace(func.coalesce(Cliente.cuit, ""), "-", "").like(digitos),
                func.coalesce(Cliente.dni, "").like(digitos),
            )
        )
        .order_by(func.coalesce(Cliente.apellido, Cliente.nombre), Cliente.nombre)
        .all()
    )


def _solo_digitos(valor: str) -> str:
    return valor.replace("-", "").replace(".", "").replace(" ", "")


def listar(db: Session, termino: str | None = None) -> list[Cliente]:
    if termino and termino.strip():
        return _buscar(db, termino)
    return (
        db.query(Cliente)
        .order_by(func.coalesce(Cliente.apellido, Cliente.nombre), Cliente.nombre)
        .all()
    )


def obtener(db: Session, cliente_id: int) -> Cliente:
    cliente = db.get(Cliente, cliente_id)
    if cliente is None:
        raise Rechazo("No existe ese cliente", 404)
    return cliente


def _verificar_unicos(db: Session, cuit: str | None, dni: str | None, excluye: int | None = None):
    if cuit:
        consulta = db.query(Cliente).filter(Cliente.cuit == cuit)
        if excluye:
            consulta = consulta.filter(Cliente.id != excluye)
        if consulta.first():
            raise Rechazo("Ya existe un cliente con ese CUIT", 409)
    if dni:
        consulta = db.query(Cliente).filter(Cliente.dni == dni)
        if excluye:
            consulta = consulta.filter(Cliente.id != excluye)
        if consulta.first():
            raise Rechazo("Ya existe un cliente con ese DNI", 409)


def _servicios_de(db: Session, ids: list[int]) -> list[Servicio]:
    if not ids:
        return []
    encontrados = db.query(Servicio).filter(Servicio.id.in_(ids)).all()
    if len(encontrados) != len(set(ids)):
        raise Rechazo("Elegiste un servicio que no existe")
    return encontrados


def crear(db: Session, datos: ClienteCrear) -> Cliente:
    _verificar_unicos(db, datos.cuit, datos.dni)
    cliente = Cliente(**datos.model_dump(exclude={"servicios"}))
    cliente.servicios = _servicios_de(db, datos.servicios)
    db.add(cliente)
    db.commit()
    db.refresh(cliente)
    return cliente


def actualizar(db: Session, cliente_id: int, datos: ClienteActualizar) -> Cliente:
    cliente = obtener(db, cliente_id)
    _verificar_unicos(db, datos.cuit, datos.dni, excluye=cliente_id)
    for campo, valor in datos.model_dump(exclude={"servicios"}).items():
        setattr(cliente, campo, valor)
    cliente.servicios = _servicios_de(db, datos.servicios)
    cliente.actualizado = datetime.utcnow()
    db.commit()
    db.refresh(cliente)
    return cliente


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
    cliente = obtener(db, cliente_id)
    if tiene_movimientos(db, cliente_id):
        raise Rechazo(
            "No se puede eliminar: el cliente ya tiene facturas, recibos "
            "o anticipos. Anulá esos movimientos o dejalo en archivo.",
            409,
        )
    # Los anticipos eliminados no son movimiento: se van con el cliente
    # para no dejar filas sueltas apuntando a un id que ya no existe.
    if inspect(db.get_bind()).has_table("anticipos"):
        db.execute(
            text("DELETE FROM anticipos WHERE cliente_id = :id AND estado = 'eliminado'"),
            {"id": cliente_id},
        )
    db.delete(cliente)
    db.commit()
