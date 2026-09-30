from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.recibo import FORMAS_PAGO
from app.schemas.factura import FacturaOut

ETIQUETAS_FORMA = {
    "transferencia": "Transferencia",
    "efectivo": "Efectivo",
    "tarjeta_credito": "Tarjeta de crédito",
    "tarjeta_debito": "Tarjeta de débito",
    "cheque": "Cheque",
    "otro": "Otro",
}


def _digitos(valor: str) -> str:
    return "".join(c for c in valor if c.isdigit())


class ReciboBase(BaseModel):
    cliente_id: int
    fecha: date
    numero: str = Field(max_length=12)
    importe: float = Field(gt=0, description="Importe en pesos")
    forma_pago: str

    @field_validator("forma_pago")
    @classmethod
    def _forma(cls, valor: str) -> str:
        if valor not in FORMAS_PAGO:
            raise ValueError("Forma de pago no válida")
        return valor

    @field_validator("numero")
    @classmethod
    def _numero(cls, valor: str) -> str:
        digitos = _digitos(valor)
        if not digitos or len(digitos) > 8:
            raise ValueError("El número de recibo tiene hasta 8 dígitos (ej.: 00000001)")
        return digitos.zfill(8)


class ReciboCrear(ReciboBase):
    pass


class ReciboActualizar(ReciboBase):
    pass


class ReciboOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cliente_id: int
    cliente_nombre: str
    fecha: date
    numero: str
    importe: float
    forma_pago: str
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
