from pydantic import BaseModel, ConfigDict, Field, field_validator


class CentroCostoCrear(BaseModel):
    nombre: str = Field(min_length=2, max_length=50)

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, valor: str) -> str:
        limpio = valor.strip()
        if not limpio:
            raise ValueError("El nombre es obligatorio")
        return limpio


class CentroCostoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    activo: bool
