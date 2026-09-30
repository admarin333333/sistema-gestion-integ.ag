from pydantic import BaseModel, ConfigDict


class LocalidadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo_postal: str
    nombre: str
    provincia: str
