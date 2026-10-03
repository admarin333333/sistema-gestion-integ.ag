from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class VarianteCrear(BaseModel):
    pantalla: str = Field(max_length=40)
    nombre: str = Field(min_length=1, max_length=60)
    filtros: dict
    compartida: bool = False


class VarianteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pantalla: str
    nombre: str
    filtros: dict
    compartida: bool
    es_mia: bool
    actualizado: datetime | None = None
