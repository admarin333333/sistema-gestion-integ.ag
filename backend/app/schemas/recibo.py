from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.recibo import FORMAS_PAGO, ESTADOS_RECIBO
from app.schemas.factura import FacturaOut

ETIQUETAS_FORMA = {
    "transferencia": "Transferencia",
    "efectivo": "Efectivo",
    "tarjeta_credito": "Tarjeta de crédito",
    "tarjeta_debito": "Tarjeta de débito",
    "cheque": "Cheque",
    "otro": "Otro",
}

ETIQUETAS_ESTADO = {
    "emitido": "Emitido",
    "anulado": "Anulado",
}


def _digitos(valor: str) -> str:
    return "".join(c for c in valor if c.isdigit())


class ReciboBase(BaseModel):
    cliente_id: int
    fecha: date
    importe: float = Field(gt=0, description="Importe en pesos")
    forma_pago: str

    @field_validator("forma_pago")
    @classmethod
    def _forma(cls, valor: str) -> str:
        if valor not in FORMAS_PAGO:
            raise ValueError("Forma de pago no válida")
        return valor


class ReciboCrear(ReciboBase):
    """Para crear: el número se genera automáticamente en el service."""
    numero: str | None = Field(default=None, max_length=8)


class ReciboActualizar(BaseModel):
    """Para actualizar: NO se puede cambiar el número."""
    fecha: date | None = None
    importe: float | None = Field(default=None, gt=0)
    forma_pago: str | None = None

    @field_validator("forma_pago")
    @classmethod
    def _forma(cls, valor: str) -> str:
        if valor and valor not in FORMAS_PAGO:
            raise ValueError("Forma de pago no válida")
        return valor


class ReciboOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cliente_id: int
    cliente_nombre: str
    fecha: date
    numero: str
    importe: float
    forma_pago: str
    estado: str
    creado: datetime
    actualizado: datetime | None = None


# ------------------------------------------------------------- aplicaciones

class AplicacionCrear(BaseModel):
    factura_id: int
    importe: float = Field(gt=0, description="Cuánto de este recibo va a esa factura")


class AplicacionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recibo_id: int
    factura_id: int
    importe: float
    factura: FacturaOut
    creado: datetime


# --------------------------------------------------------- cuenta corriente

class MovimientoOut(BaseModel):
    fecha: date
    concepto: str
    debe: float
    haber: float
    saldo: float


class CuentaCorrienteOut(BaseModel):
    cliente_id: int
    cliente_nombre: str
    movimientos: list[MovimientoOut]
    total_debe: float
    total_haber: float
    saldo: float
