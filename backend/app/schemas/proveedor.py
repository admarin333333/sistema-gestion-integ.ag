from pydantic import BaseModel

from app.schemas.persona import PersonaOut


class ProveedorBase(BaseModel):
    nro_cuenta: int


class ProveedorCreate(ProveedorBase):
    persona_id: int


class ProveedorOut(ProveedorBase):
    id: int
    persona: PersonaOut

    model_config = {"from_attributes": True}