from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

_ESTADOS = ("pendiente", "atendida")


def _solo_digitos(valor: str) -> str:
    return valor.replace("-", "").replace(".", "").replace(" ", "")


class SugerenciaBase(BaseModel):
    fecha: date = Field(description="Fecha de la sugerencia")
    descripcion: str = Field(min_length=3, max_length=500)
    estado: str = "pendiente"

    @field_validator("descripcion")
    @classmethod
    def _sin_vacio(cls, valor: str) -> str:
        limpio = valor.strip()
        if not limpio:
            raise ValueError("La descripción no puede estar vacía")
        return limpio

    @field_validator("estado")
    @classmethod
    def _estado_valido(cls, valor: str) -> str:
        if valor not in _ESTADOS:
            raise ValueError(f"El estado debe ser uno de: {', '.join(_ESTADOS)}")
        return valor


class SugerenciaCrear(SugerenciaBase):
    pass


class SugerenciaActualizar(SugerenciaBase):
    pass


class SugerenciaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cliente_id: int
    fecha: date
    descripcion: str
    estado: str
    creado: datetime
