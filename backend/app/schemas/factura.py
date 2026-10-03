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

# Qué cuenta de ingresos va en el Haber del asiento. El contador elige; de
# ahí sale la clave de `config_asientos` (VENTA_SERVICIOS_* / VENTA_ARTICULOS_*).
OPERACIONES = {"SERVICIOS": "Servicios", "ARTICULOS": "Artículos"}


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
    # Si esta factura es una NOTA (de crédito o de débito), cuál corrige. Va en
    # NULL para las facturas normales.
    #
    # El tipo y el signo del asiento los decide el backend a partir del
    # `tipo_comprobante`: una nota de crédito pone los ingresos en el Debe.
    factura_relacionada_id: int | None = None
    fecha_vencimiento: date | None = None
    condicion_venta: str = "contado"
    # ARCA — opcionales en esta versión
    cae: str | None = Field(default=None, max_length=20)
    cae_vencimiento: date | None = None

    # --- Para el asiento contable -----------------------------------
    # Servicios o artículos: decide a qué cuenta de ingresos va el Haber.
    tipo_operacion: str = "SERVICIOS"
    # La alícuota de IVA. El NETO y el IVA **no se mandan**: los desglosa el
    # backend a partir del importe y esta alícuota. El navegador no calcula
    # nada contable.
    alicuota_iva_id: int | None = None

    # --- Libro de IVA Ventas (ver `migrar_iva_ventas.py`) ---
    #
    # Los dos que el libro necesita como columna propia. El `importe` sigue
    # siendo el total con IVA: `percepcion` y `no_gravado` son INFORMATIVOS y
    # no cambian el total del comprobante, por eso van aparte. Si se sumaran al
    # `importe`, el neto del libro dejaría de cuadrar con la factura.
    #
    # A diferencia del neto y el IVA, estos **sí se mandan**: son datos que el
    # contador conoce y la base no puede deducirlos del importe.
    percepcion: float = Field(default=0, ge=0, description="IVA retenido por el cliente")
    no_gravado: float = Field(default=0, ge=0, description="Parte del total sin IVA")

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

    @field_validator("tipo_operacion")
    @classmethod
    def _operacion(cls, valor: str) -> str:
        if valor not in OPERACIONES:
            raise ValueError("Tipo de operación no válido")
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


class FacturaPreview(BaseModel):
    """Lo mismo que la factura, pero para PREVISUALIZAR el asiento.

    No guarda nada: la pantalla lo manda mientras se carga el formulario para
    ver cómo va a quedar el asiento, y recién al apretar "OK, facturar" se
    crea la factura de verdad.

    Todos los campos son opcionales salvo el cliente y el importe, que son los
    dos sin los cuales no hay nada que proyectar.

    El `tipo_comprobante` SÍ importa acá: si es una nota de crédito, el preview
    muestra el asiento al revés (ingresos en el Debe) y el código `NC` en vez de
    `FV`. Por eso no se puede hardcodear `factura_b`.
    """

    cliente_id: int | None = None
    fecha: date = Field(default_factory=date.today)
    tipo_comprobante: str = "factura_b"
    punto_venta: str | None = None
    numero: str | None = None
    concepto: str | None = None
    importe: float | None = None
    condicion_venta: str = "contado"
    tipo_operacion: str = "SERVICIOS"
    alicuota_iva_id: int | None = None
    factura_relacionada_id: int | None = None

    @field_validator("tipo_operacion")
    @classmethod
    def _operacion(cls, valor: str) -> str:
        if valor not in OPERACIONES:
            raise ValueError("Tipo de operación no válido")
        return valor


class FacturaActualizar(FacturaBase):
    pass


class FacturaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cliente_id: int
    cliente_nombre: str
    # La factura que esta nota corrige, si es una nota.
    factura_relacionada_id: int | None = None
    fecha: date
    tipo_comprobante: str
    punto_venta: str
    numero: str
    concepto: str | None = None
    importe: float
    aplicado: float = 0
    fecha_vencimiento: date | None = None
    condicion_venta: str
    estado: str
    cae: str | None = None
    cae_vencimiento: date | None = None
    fecha_envio: datetime | None = None
    creado: datetime
    actualizado: datetime | None = None

    # --- Asiento contable ---
    # El desglose que calculó el backend. `importe = neto + iva` siempre.
    tipo_operacion: str = "SERVICIOS"
    neto: float | None = None
    iva: float | None = None
    alicuota_iva_id: int | None = None
    alicuota_iva_aplicada: float | None = None

    # --- Libro de IVA Ventas ---
    # **Opcionales a propósito.** Las facturas anteriores a la migración tienen
    # NULL acá (la columna se agregó después): si se declararan `float = 0`, Pydantic
    # rechazaría el NULL y el listado de facturas del cliente devolvería 500 sin
    # explicación. El NULL además significa algo: "nunca se cargó", que no es lo
    # mismo que "se cargó en cero".
    #
    # Sin esto no se podrían editar: al abrir una factura para corregirla, los
    # dos campos del formulario saldrían vacíos y, si se guardara, se pondrían
    # en 0 pisando lo que estaba cargado.
    percepcion: float | None = None
    no_gravado: float | None = None

    # El asiento que se generó a partir de esta factura, si hay. La pantalla
    # usa esto para mostrar los botones Generar / Modificar / Anular.
    id_asiento: int | None = None
    estado_asiento: str | None = None
    numero_comprobante_asiento: str | None = None

    # Lo que hay que avisarle al contador al cargar una nota: por ejemplo que
    # la factura que corrige ya estaba pagada. No bloquean, se muestran.
    avisos: list[str] = Field(default_factory=list)


class EnvioMasivo(BaseModel):
    """Lo que manda el botón: los IDs de las facturas a enviar."""

    ids: list[int] = Field(min_length=1)


class EnvioResultado(BaseModel):
    enviadas: int
    avisos: list[str]
