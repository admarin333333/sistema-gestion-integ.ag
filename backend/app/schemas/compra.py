from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.compra import ESTADOS_COMPRA
from app.models.factura import TIPOS_COMPROBANTE
from app.schemas.alicuota import AlicuotaOut
from app.schemas.factura import ETIQUETAS_TIPO
from app.schemas.plan_cuenta import PlanCuentaOut

ETIQUETAS_ESTADO_COMPRA = {
    "pendiente": "Pendiente",
    "anulada": "Anulada",
}


def _digitos(valor: str) -> str:
    return "".join(c for c in valor if c.isdigit())


class CompraBase(BaseModel):
    proveedor_id: int
    fecha: date
    tipo_comprobante: str
    punto_venta: str = Field(max_length=10)
    numero: str = Field(max_length=12)
    concepto: str | None = Field(default=None, max_length=200)
    neto: float = Field(gt=0, description="Importe neto en pesos")
    alicuota_iva_id: int
    percepcion_iva: float = Field(default=0, ge=0, description="Percepción IVA en pesos")
    # La cuenta de GASTO del plan (6.1.03 luz-agua, 6.2.01 publicidad...). Es lo
    # único que decide dónde cae el gasto: el centro de costos sale de esta
    # cuenta, no de una lista aparte. El backend verifica que sea imputable y
    # que esté bajo la rama 6 (GASTOS).
    cuenta_gasto_id: int = Field(
        description="Cuenta de gasto del plan: 6.x.x"
    )
    fecha_vencimiento: date | None = None

    @field_validator("tipo_comprobante")
    @classmethod
    def _tipo(cls, valor: str) -> str:
        if valor not in TIPOS_COMPROBANTE:
            raise ValueError("Tipo de comprobante no válido")
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


class CompraCrear(CompraBase):
    pass


class CompraActualizar(CompraBase):
    pass


class CompraOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    proveedor_id: int
    proveedor_nombre: str
    fecha: date
    tipo_comprobante: str
    punto_venta: str
    numero: str
    concepto: str | None = None
    neto: float
    alicuota_iva_id: int
    alicuota: AlicuotaOut | None = None
    iva: float
    percepcion_iva: float
    total: float

    # La cuenta de gasto del plan. `cuenta_gasto` trae el código y el nombre
    # para que la pantalla muestre "6.1.03 luz-agua" y no un número.
    cuenta_gasto_id: int | None = None
    cuenta_gasto: PlanCuentaOut | None = None
    # El centro de costos NO se elige: sale de la cuenta de gasto.
    centro_nombre: str = ""

    fecha_vencimiento: date | None = None
    estado: str
    # El asiento: si la compra ya está en los libros, cuál es y en qué estado.
    id_asiento: int | None = None
    estado_asiento: str | None = None
    numero_comprobante_asiento: str | None = None
    creado: datetime
    actualizado: datetime | None = None


class CompraPreviewIn(BaseModel):
    """Lo que manda la pantalla para ver el asiento ANTES de generarlo.

    Se manda la compra entera (no un id) porque el preview tiene que servir
    también para una compra que todavía no se guardó: el contador elige la
    cuenta, mira cómo queda el asiento y recién ahí le da OK.
    """

    proveedor_id: int
    proveedor_nombre: str | None = None
    fecha: date
    tipo_comprobante: str
    punto_venta: str = Field(max_length=10)
    numero: str = Field(max_length=12)
    concepto: str | None = Field(default=None, max_length=200)
    neto: float = Field(gt=0)
    iva: float = Field(ge=0)
    percepcion_iva: float = Field(default=0, ge=0)
    total: float = Field(gt=0)
    cuenta_gasto_id: int
