from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.centrocosto import CentroCostoOut


class TipoGastoCrear(BaseModel):
    nombre: str = Field(min_length=2, max_length=50)
    centro_costo_id: int

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, valor: str) -> str:
        limpio = valor.strip()
        if not limpio:
            raise ValueError("El nombre es obligatorio")
        return limpio


class TipoGastoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    centro_costo_id: int
    centro: CentroCostoOut | None = None
    activo: bool
