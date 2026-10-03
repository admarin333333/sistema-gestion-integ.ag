import json
from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.errors import Rechazo
from app.models.usuario import Usuario
from app.models.variante import Variante
from app.schemas.variante import VarianteCrear

# Pantallas que pueden guardar variantes (validación de seguridad).
PANTALLAS = (
    "informe-resultados",
    "informe-centros",
    "compras",
    "clientes",
    "proveedores",
    "dashboard",
)

_LIMITE_FILTROS = 5000  # caracteres del JSON


def _a_dict(fila: Variante, usuario: Usuario) -> dict:
    return {
        "id": fila.id,
        "pantalla": fila.pantalla,
        "nombre": fila.nombre,
        "filtros": json.loads(fila.filtros),
        "compartida": fila.compartida,
        "es_mia": fila.usuario_id == usuario.id,
        "actualizado": fila.actualizado,
    }


def _validar_pantalla(pantalla: str) -> None:
    if pantalla not in PANTALLAS:
        raise Rechazo("Pantalla no válida para variantes", 400)


def listar(db: Session, pantalla: str, usuario: Usuario) -> list[dict]:
    """Las mías de esa pantalla + las compartidas por otros."""
    _validar_pantalla(pantalla)
    filas = (
        db.query(Variante)
        .filter(
            Variante.pantalla == pantalla,
            or_(Variante.usuario_id == usuario.id, Variante.compartida.is_(True)),
        )
        .order_by(Variante.nombre.asc())
        .all()
    )
    return [_a_dict(f, usuario) for f in filas]


def guardar(db: Session, datos: VarianteCrear, usuario: Usuario) -> dict:
    """Si ya existe mi variante con ese nombre, se sobreescribe (como en SAP)."""
    _validar_pantalla(datos.pantalla)
    nombre = datos.nombre.strip()
    if not nombre:
        raise Rechazo("El nombre de la variante es obligatorio", 400)

    texto = json.dumps(datos.filtros, ensure_ascii=False)
    if len(texto) > _LIMITE_FILTROS:
        raise Rechazo("Los filtros de la variante son demasiado grandes", 400)

    fila = (
        db.query(Variante)
        .filter(
            Variante.usuario_id == usuario.id,
            Variante.pantalla == datos.pantalla,
            Variante.nombre == nombre,
        )
        .first()
    )
    if fila:
        fila.filtros = texto
        fila.compartida = datos.compartida
        fila.actualizado = datetime.utcnow()
    else:
        fila = Variante(
            usuario_id=usuario.id,
            pantalla=datos.pantalla,
            nombre=nombre,
            filtros=texto,
            compartida=datos.compartida,
        )
        db.add(fila)
    db.commit()
    db.refresh(fila)
    return _a_dict(fila, usuario)


def eliminar(db: Session, variante_id: int, usuario: Usuario) -> None:
    fila = db.get(Variante, variante_id)
    if fila is None:
        raise Rechazo("No existe esa variante", 404)
    if fila.usuario_id != usuario.id and usuario.rol != "admin":
        raise Rechazo("Solo podés borrar tus propias variantes", 403)
    db.delete(fila)
    db.commit()
