from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.factura import FacturaOut


# Para que los informes muestren "Disponible" en vez del código "disponible".
ETIQUETAS_ESTADO = {
    "disponible": "Disponible",
    "parcial": "Parcial",
    "aplicado": "Aplicado",
    "eliminado": "Eliminado",
}


class AnticipoBase(BaseModel):
    cliente_id: int
    fecha: date
    importe: float = Field(gt=0, description="Importe adelantado en pesos")


class AnticipoCrear(AnticipoBase):
    """Para crear: el número se genera automáticamente en el service."""
    numero: str | None = Field(default=None, max_length=8)


class AnticipoActualizar(BaseModel):
    """Para actualizar: NO se puede cambiar el número."""
    fecha: date | None = None
    importe: float | None = Field(default=None, gt=0)


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


# ------------------------------------------------------------- aplicaciones

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