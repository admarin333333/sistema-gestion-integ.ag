from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ServicioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    orden: int = 0


class ServicioCrear(BaseModel):
    """Alta de un servicio del catálogo.

    `orden` es opcional: si no viene, el backend le pone el último + 1 para que
    el servicio nuevo quede al final del formulario sin desordenar el resto.
    """

    nombre: str = Field(min_length=2, max_length=80)
    orden: Optional[int] = None

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, valor: str) -> str:
        # "   " pasa el min_length (tiene 3 caracteres) pero no es un nombre.
        limpio = valor.strip()
        if not limpio:
            raise ValueError("El nombre del servicio no puede estar vacío")
        return limpio
