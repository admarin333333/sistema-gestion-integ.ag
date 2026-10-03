"""Clave fiscal de ARCA: fechas y cuaderno de cambios.

La clave fiscal va en `personas` (junto al CUIT) y tiene tres fechas:
- `fecha_carga_clave_fiscal`: cuándo se cargó **por primera vez**.
- `fecha_modif_clave_fiscal`: cuándo se cambió por **última vez**.

Además, cada vez que la clave **cambia** (o se carga por primera vez) se
agrega una fila a `clave_fiscal_historial` con la clave anterior y la nueva.
Si la clave nunca cambió, la persona no tiene filas en el historial.
"""

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import Rechazo
from app.models.clave_fiscal import ClaveFiscalHistorial

LARGO_CLAVE_FISCAL = 11


def normalizar(valor: str | None) -> str | None:
    """Limpia la clave: sin espacios, en mayúsculas. Vacía -> None."""
    if valor is None:
        return None
    v = "".join(valor.split()).upper()
    return v or None


def _validar(valor: str | None) -> str | None:
    v = normalizar(valor)
    if v is None:
        return None
    if len(v) != LARGO_CLAVE_FISCAL:
        raise Rechazo(
            f"La clave fiscal debe tener {LARGO_CLAVE_FISCAL} caracteres "
            f"(tiene {len(v)}).",
            400,
        )
    if not v.isalnum():
        raise Rechazo("La clave fiscal solo puede tener letras y números.", 400)
    return v


def aplicar(persona, nueva: str | None, usuario: str | None = None) -> bool:
    """Pone la clave fiscal en la persona y deja las fechas al día.

    Devuelve True si la clave **cambió** (y se registró en el historial).
    No toca nada ni crea historial si viene igual que la que ya tenía.
    """
    valor = _validar(nueva)
    anterior = normalizar(persona.clave_fiscal)
    if valor == anterior:
        return False

    ahora = datetime.utcnow()
    persona.clave_fiscal = valor

    if valor is None:
        # Se borró: no hay fecha de carga ni de modificación.
        persona.fecha_carga_clave_fiscal = None
        persona.fecha_modif_clave_fiscal = None
        return True

    # Primera vez que se carga -> fecha de carga; además es una modificación.
    if persona.fecha_carga_clave_fiscal is None:
        persona.fecha_carga_clave_fiscal = date.today()
    persona.fecha_modif_clave_fiscal = ahora
    return True


def registrar_cambio(
    db: Session,
    persona,
    anterior: str | None,
    nueva: str | None,
    usuario: str | None = None,
) -> ClaveFiscalHistorial | None:
    """Deja una fila en el historial (la usa el service de clientes)."""
    if anterior == nueva:
        return None
    fila = ClaveFiscalHistorial(
        persona_id=persona.id,
        clave_fiscal_anterior=anterior,
        clave_fiscal_nueva=nueva,
        fecha_cambio=datetime.utcnow(),
        usuario=usuario,
    )
    db.add(fila)
    return fila


def historial(db: Session, persona_id: int) -> list[dict]:
    """Los cambios de clave fiscal de una persona, del más nuevo al más viejo."""
    filas = db.execute(
        select(ClaveFiscalHistorial)
        .where(ClaveFiscalHistorial.persona_id == persona_id)
        .order_by(ClaveFiscalHistorial.fecha_cambio.desc(), ClaveFiscalHistorial.id.desc())
    ).scalars().all()
    return [
        {
            "id": f.id,
            "clave_fiscal_anterior": f.clave_fiscal_anterior,
            "clave_fiscal_nueva": f.clave_fiscal_nueva,
            "fecha_cambio": f.fecha_cambio,
            "usuario": f.usuario,
        }
        for f in filas
    ]