from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.factura import CONDICIONES_VENTA, ESTADOS, TIPOS_COMPROBANTE

ETIQUETAS_TIPO = {
    "factura_a": "Factura A",
    "factura_b": "Factura B",
    "factura_c": "Factura C",
    "nota_credito_a": "Nota de crédito A",
    "nota_credito_b": "Nota de crédito B",
    "nota_credito_c": "Nota de crédito C",
    "nota_debito_a": "Nota de débito A",
    "nota_debito_b": "Nota de débito B",
    "nota_debito_c": "Nota de débito C",
}

ETIQUETAS_CONDICION = {
    "contado": "Contado",
    "cta_corriente_15": "Cta. corriente 15 días",
    "cta_corriente_30": "Cta. corriente 30 días",
}

ETIQUETAS_ESTADO = {
    "pendiente": "Pendiente",
    "parcial": "Parcialmente pagada",
    "pagada": "Pagada",
    "anulada": "Anulada",
}


def _digitos(valor: str) -> str:
    return "".join(c for c in valor if c.isdigit())


class FacturaBase(BaseModel):
    cliente_id: int
    fecha: date
    tipo_comprobante: str
    punto_venta: str = Field(max_length=10)
    numero: str = Field(max_length=12)
    concepto: str | None = Field(default=None, max_length=200)
    importe: float = Field(gt=0, description="Importe en pesos")
    fecha_vencimiento: date | None = None
    condicion_venta: str = "contado"
    # ARCA — opcionales en esta versión
    cae: str | None = Field(default=None, max_length=20)
    cae_vencimiento: date | None = None

    @field_validator("tipo_comprobante")
    @classmethod
    def _tipo(cls, valor: str) -> str:
        if valor not in TIPOS_COMPROBANTE:
            raise ValueError("Tipo de comprobante no válido")
        return valor

    @field_validator("condicion_venta")
    @classmethod
    def _condicion(cls, valor: str) -> str:
        if valor not in CONDICIONES_VENTA:
            raise ValueError("Condición de venta no válida")
        return valor

    @field_validator("punto_venta")
    @classmethod
    def _punto_venta(cls, valor: str) -> str:
        digitos = _digitos(valor)
        if not digitos or len(digitos) > 4:
            raise ValueError("El punto de venta tiene hasta 4 dígitos (ej.: 0001)")
        return digitos.zfill(4)

    @field_validator("numero")
    @classmethod
    def _numero(cls, valor: str) -> str:
        digitos = _digitos(valor)
        if not digitos or len(digitos) > 8:
            raise ValueError("El número tiene hasta 8 dígitos (ej.: 00000001)")
        return digitos.zfill(8)

    @field_validator("concepto", mode="before")
    @classmethod
    def _vacio(cls, valor):
        if isinstance(valor, str) and not valor.strip():
            return None
        return valor

    @field_validator("cae")
    @classmethod
    def _cae(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        digitos = _digitos(valor)
        if not digitos:
            return None
        if len(digitos) > 20:
            raise ValueError("El CAE tiene hasta 20 dígitos")
        return digitos


class FacturaCrear(FacturaBase):
    pass


class FacturaActualizar(FacturaBase):
    pass


class FacturaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cliente_id: int
    cliente_nombre: str
    fecha: date
    tipo_comprobante: str
    punto_venta: str
    numero: str
    concepto: str | None = None
    importe: float
    fecha_vencimiento: date | None = None
    condicion_venta: str
    estado: str
    cae: str | None = None
    cae_vencimiento: date | None = None
    fecha_envio: datetime | None = None
    creado: datetime
    actualizado: datetime | None = None


class EnvioMasivo(BaseModel):
    """Lo que manda el botón: los IDs de las facturas a enviar."""

    ids: list[int] = Field(min_length=1)


class EnvioResultado(BaseModel):
    enviadas: int
    avisos: list[str]
