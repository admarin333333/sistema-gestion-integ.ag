from datetime import date

from pydantic import BaseModel, Field


class IndiceCrear(BaseModel):
    """Alta o corrección de un índice: si el mes ya existe, se actualiza."""

    fecha: date
    indice: float = Field(gt=0)


class IndiceOut(BaseModel):
    id: int
    fecha: date
    indice: float
