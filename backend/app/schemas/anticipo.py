from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.anticipo import ESTADOS_ANTICIPO
from app.schemas.factura import FacturaOut


# Para que los informes muestren "Disponible" en vez del código "disponible".
ETIQUETAS_ESTADO = {
    "disponible": "Disponible",
    "parcial": "Parcial",
    "aplicado": "Aplicado",
    "eliminado": "Eliminado",
}


def _digitos(valor: str) -> str:
    return "".join(c for c in valor if c.isdigit())


class AnticipoBase(BaseModel):
    cliente_id: int
    fecha: date
    numero: str = Field(max_length=12)
    importe: float = Field(gt=0, description="Importe adelantado en pesos")

    @field_validator("numero")
    @classmethod
    def _numero(cls, valor: str) -> str:
        digitos = _digitos(valor)
        if not digitos or len(digitos) > 8:
            raise ValueError("El número de anticipo tiene hasta 8 dígitos (ej.: 00000001)")
        return digitos.zfill(8)


class AnticipoCrear(AnticipoBase):
    pass


class AnticipoActualizar(AnticipoBase):
    pass


class AnticipoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cliente_id: int
    cliente_nombre: str
    fecha: date
    numero: str
    importe: float
    estado: str
    creado: datetime
    actualizado: datetime | None = None


class AplicacionAnticipoCrear(BaseModel):
    factura_id: int
    importe: float = Field(gt=0, description="Cuánto de este anticipo va a esa factura")


class AplicacionAnticipoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    anticipo_id: int
    factura_id: int
    importe: float
    factura: FacturaOut
    creado: datetime
