from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import Rechazo
from app.models.propietario import Propietario

CAMPOS = (
    "nombre", "cuit", "actividad",
    "calle", "numero_calle", "localidad", "provincia", "codigo_postal",
    "telefono", "cod_area",
    "email_1", "email_2", "email_3", "email_4",
    "aviso_vencimientos", "observaciones",
)


def _validar_correo(valor: str | None) -> str | None:
    if valor is None:
        return None
    v = valor.strip()
    if not v:
        return None
    if "@" not in v or "." not in v.split("@")[-1]:
        raise Rechazo(f"El correo «{v}» no es válido", 400)
    return v


def obtener(db: Session) -> Propietario:
    """La única fila de propietario (si no existe, se crea vacía)."""
    p = db.execute(select(Propietario).limit(1)).scalar_one_or_none()
    if p is None:
        p = Propietario(nombre="")
        db.add(p)
        db.commit()
        db.refresh(p)
    return p


def guardar(db: Session, datos: dict) -> Propietario:
    p = obtener(db)
    for i in (1, 2, 3, 4):
        if f"email_{i}" in datos:
            valor = _validar_correo(datos.get(f"email_{i}"))
            setattr(p, f"email_{i}", valor)
    for campo in CAMPOS:
        if campo.startswith("email_"):
            continue
        if campo in datos:
            setattr(p, campo, datos[campo])
    p.actualizado = datetime.utcnow()
    db.commit()
    db.refresh(p)
    return p


def a_json(p: Propietario) -> dict:
    datos = {campo: getattr(p, campo) for campo in CAMPOS}
    datos["id"] = p.id
    datos["correos"] = p.correos
    datos["domicilio"] = p.domicilio
    datos["tiene_correo"] = bool(p.correos)
    return datos