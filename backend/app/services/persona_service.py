from sqlalchemy.orm import Session

from app.models.persona import Persona
from app.schemas.persona import PersonaCreate, PersonaUpdate


def listar_personas(db: Session) -> list[Persona]:
    return db.query(Persona).all()


def obtener_persona(db: Session, persona_id: int) -> Persona | None:
    return db.get(Persona, persona_id)


def crear_persona(db: Session, datos: PersonaCreate) -> Persona:
    persona = Persona(**datos.model_dump())
    db.add(persona)
    db.commit()
    db.refresh(persona)
    return persona


def actualizar_persona(db: Session, persona_id: int, datos: PersonaUpdate) -> Persona | None:
    persona = db.get(Persona, persona_id)
    if not persona:
        return None
    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(persona, campo, valor)
    db.commit()
    db.refresh(persona)
    return persona


def eliminar_persona(db: Session, persona_id: int) -> bool:
    persona = db.get(Persona, persona_id)
    if not persona:
        return False
    db.delete(persona)
    db.commit()
    return True