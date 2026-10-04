"""
Schemas de cuentas bancarias.

Van aparte del schema de clientes a propósito: las cuentas son su propia cosa,
con su propia tabla y su propia API. Meterlas en el `ClienteIn`/`ClienteOut`
obligaría a que TODAS las pantallas de cliente cargaran y mostraran cuentas
bancarias, aunque solo la ficha las use.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.cta_bancaria import MONEDAS


class BancoIn(BaseModel):
    codigo: str = Field(..., min_length=8, max_length=8)
    nombre: str = Field(..., min_length=1, max_length=80)

    @field_validator("codigo")
    @classmethod
    def _codigo(cls, v: str) -> str:
        v = v.strip()
        if not v.isdigit():
            raise ValueError("El código del banco tiene que ser 8 dígitos numéricos")
        return v


class BancoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    codigo: str
    nombre: str
    activo: bool


class CtaBancariaIn(BaseModel):
    """
    Alta o modificación de una cuenta.

    **Al menos uno de `cbu`, `cvu` o `alias_cbu`**, y nunca `cbu` y `cvu` juntos.
    Eso no se valida acá sino en el service: el schema no sabe qué es un CBU, y
    el motivo del rechazo tiene que ser el texto que ve el contador, no el error
    técnico de Pydantic.
    """

    codigo_banco: str | None = Field(default=None, max_length=8)
    sucursal: str | None = Field(default=None, max_length=10)
    numero_cuenta: str | None = Field(default=None, max_length=30)
    cbu: str | None = Field(default=None, max_length=22)
    cvu: str | None = Field(default=None, max_length=22)
    alias_cbu: str | None = Field(default=None, max_length=40)
    cuit_titular: str | None = Field(default=None, max_length=13)
    moneda: str = Field(default="ARS", max_length=3)

    @field_validator("moneda")
    @classmethod
    def _moneda(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in MONEDAS:
            raise ValueError(f"La moneda tiene que ser {' o '.join(MONEDAS)}")
        return v


class CtaBancariaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    id_cliente: int
    codigo_banco: str
    nombre_banco: str | None = None
    sucursal: str | None = None
    numero_cuenta: str | None = None
    cbu: str | None = None
    cvu: str | None = None
    alias_cbu: str | None = None
    cuit_titular: str | None = None
    moneda: str
    activo: bool
    # Qué se copia al portapapeles: una sola cosa, no las dos.
    para_cobrar: str | None = None
    tipo: str = "Alias"


class BancoDesdeCBUOut(BaseModel):
    """Qué banco es este CBU. Para cargar el catálogo la primera vez."""

    codigo: str
    nombre: str | None = None
    ya_cargado: bool