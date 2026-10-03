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
    # En qué cuenta entró la plata. Es OPCIONAL: si viene en NULL, se usa la
    # cuenta de cobro fija de Configuración. Si viene con un id, gana ese (para
    # el caso de que haya más de una y esta entre por otra).
    #
    # OJO: si el recibo trae `pagos`, esta cuenta queda como simple respaldo y
    # el Debe del asiento sale de los pagos (uno por forma de pago).
    cuenta_cobro_id: int | None = None

    @field_validator("forma_pago")
    @classmethod
    def _forma(cls, valor: str) -> str:
        if valor not in FORMAS_PAGO:
            raise ValueError("Forma de pago no válida")
        return valor


class ReciboCrear(ReciboBase):
    """Para crear: el número lo genera el service.

    `numero` está acá solo para poder contestarle al usuario que no se carga a
    mano (si viene, el service lo rechaza con un mensaje claro).
    """
    numero: str | None = Field(default=None, max_length=8)
    # Con qué se pagó, cuando el recibo se cobra con más de un medio. Vacío =
    # recibo de una sola forma de pago, que usa `cuenta_cobro_id` como antes.
    pagos: list["PagoIn"] = Field(default_factory=list)
    # Las facturas que se cobran con este recibo (las que tildó el contador).
    # El backend reparte el `importe` entre ellas, de la más vieja a la más
    # nueva y sin pasarse del saldo de ninguna. Vacío = recibo sin aplicar
    # todavía (adelanto), que se aplica después desde la pantalla del recibo.
    facturas: list[int] = Field(default_factory=list)


class ReciboActualizar(BaseModel):
    """Para actualizar: NO se puede cambiar el número."""
    fecha: date | None = None
    importe: float | None = Field(default=None, gt=0)
    forma_pago: str | None = None
    cuenta_cobro_id: int | None = None

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
    # La cuenta donde entró la plata, ya resuelta (la que vino en el recibo o,
    # si vino en NULL, la fija de Configuración). Con el código y el nombre
    # para que la pantalla no tenga que ir a buscarlos.
    #
    # OJO: con los recibos que tienen pagos, esta cuenta es solo un respaldo.
    # El Debe del asiento sale de `pagos`, uno por forma de pago.
    cuenta_cobro_id: int | None = None
    cuenta_cobro_codigo: str | None = None
    cuenta_cobro_nombre: str | None = None
    # Los pagos, cuando los hay. Vacío en los recibos cargados antes de la
    # tabla `recibo_pagos`.
    pagos: list["PagoOut"] = Field(default_factory=list)
    # El asiento de cobranza, si se generó. La pantalla muestra el
    # comprobante en la columna y ofrece Generar / Anular según `estado_asiento`.
    id_asiento: int | None = None
    estado_asiento: str | None = None
    numero_comprobante_asiento: str | None = None
    creado: datetime
    actualizado: datetime | None = None


# --------------------------------------------------------------- pagos

class PagoIn(BaseModel):
    """Una forma de pago del recibo.

    `cuenta_id` va en NULL cuando la forma de pago es de las que NO tienen
    cuenta fija (transferencia, tarjeta de débito, otro): ahí tiene que elegir
    el banco. El backend avisa si intenta asentar sin elegirlo.
    """

    forma_pago: str
    importe: float = Field(gt=0, description="Cuánto se paga con este medio")
    cuenta_id: int | None = None
    detalle: str | None = Field(default=None, max_length=200)

    @field_validator("forma_pago")
    @classmethod
    def _forma(cls, valor: str) -> str:
        if valor not in FORMAS_PAGO:
            raise ValueError("Forma de pago no válida")
        return valor

    @field_validator("detalle", mode="before")
    @classmethod
    def _vacio(cls, valor):
        if isinstance(valor, str) and not valor.strip():
            return None
        return valor


class PagoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_pago: int
    recibo_id: int
    forma_pago: str
    importe: float
    cuenta_id: int | None = None
    cuenta_codigo: str | None = None
    cuenta_nombre: str | None = None
    detalle: str | None = None


class FormaPagoConfigOut(BaseModel):
    """De `config_cuentas_forma_pago`: qué cuenta va por forma de pago.

    `requiere_banco = true` significa que la cuenta NO está fija y el contador
    tiene que elegirla (el banco). La pantalla usa esto para mostrar el
    desplegable solo cuando hace falta.
    """

    forma_pago: str
    cuenta_id: int | None = None
    cuenta_codigo: str | None = None
    cuenta_nombre: str | None = None
    requiere_banco: bool
    descripcion: str | None = None


# ------------------------------------------------------- vista previa del cobro

class CobroPreviewIn(BaseModel):
    """Lo que la pantalla manda para ver cómo quedaría el recibo.

    `facturas` son los IDs tildados. `importe` es el NETO que se ve en pantalla
    (puede venir editado a mano, por si el cliente paga de más). `pagos` son las
    formas de pago con su cuenta.

    El backend reparte el importe entre las facturas y arma el asiento: el
    navegador no hace ninguna cuenta.
    """

    cliente_id: int
    fecha: date
    importe: float = Field(gt=0, description="Importe en pesos")
    facturas: list[int] = Field(default_factory=list)
    pagos: list[PagoIn] = Field(default_factory=list)
    # La forma de pago "principal" del recibo. Es un campo que la base exige
    # (una sola palabra); con varias filas manda la primera.
    forma_pago: str = "transferencia"

    @field_validator("forma_pago")
    @classmethod
    def _forma(cls, valor: str) -> str:
        if valor not in FORMAS_PAGO:
            raise ValueError("Forma de pago no válida")
        return valor


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
