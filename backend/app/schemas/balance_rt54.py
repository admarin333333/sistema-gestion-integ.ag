from datetime import date

from pydantic import BaseModel, Field, field_validator

SECCIONES = ("esp", "er", "eepn")


class EjercicioCrear(BaseModel):
    cliente_id: int
    nombre: str = Field(min_length=1, max_length=60)
    # Si mandan los años del ejercicio, el backend arma el intervalo y estas
    # dos fechas no hacen falta. Si no, se usan tal cual vienen.
    fecha_inicio: date | None = None
    fecha_fin: date | None = None
    # Ejercicio contable: el usuario elige los años; el día/mes de cierre sale
    # de la ficha del cliente. Si vienen, el backend arma el intervalo.
    anio_inicio: int | None = Field(default=None, ge=1900, le=2999)
    anio_fin: int | None = Field(default=None, ge=1900, le=2999)
    dia_mes_cierre: int | None = Field(default=None, ge=1, le=31)
    mes_cierre: int | None = Field(default=None, ge=1, le=12)
    # Carátula: si no mandan nada, se copia de la ficha del cliente.
    entidad: str | None = Field(default=None, max_length=120)
    cuit: str | None = Field(default=None, max_length=13)
    domicilio: str | None = Field(default=None, max_length=160)
    actividad: str | None = Field(default=None, max_length=120)
    actividad_secundaria: str | None = Field(default=None, max_length=160)


class CabeceraActualizar(BaseModel):
    nombre: str = Field(min_length=1, max_length=60)
    fecha_inicio: date
    fecha_fin: date
    entidad: str = Field(default="", max_length=120)
    cuit: str | None = Field(default=None, max_length=13)
    domicilio: str | None = Field(default=None, max_length=160)
    actividad: str | None = Field(default=None, max_length=120)
    actividad_secundaria: str | None = Field(default=None, max_length=160)

    # Registro Público de Comercio (fechas "AAAA-MM-DD" o vacío).
    fecha_inscripcion_rpc: str | None = Field(default=None, max_length=10)
    fecha_estatuto: str | None = Field(default=None, max_length=10)
    fecha_modificacion_estatuto: str | None = Field(default=None, max_length=10)
    fecha_vencimiento_entidad: str | None = Field(default=None, max_length=10)
    matricula_rpc: str | None = Field(default=None, max_length=40)
    identificacion_rpc: str | None = Field(default=None, max_length=120)
    duracion_entidad: int | None = None
    unidad_medida: str | None = Field(default=None, max_length=60)

    # Sociedad controlante y entes controlados.
    controlante_denominacion: str | None = Field(default=None, max_length=120)
    controlante_domicilio: str | None = Field(default=None, max_length=160)
    controlante_actividad: str | None = Field(default=None, max_length=120)
    controlante_participacion: str | None = Field(default=None, max_length=40)
    controlante_votos: str | None = Field(default=None, max_length=40)
    entes_nota: str | None = Field(default=None, max_length=10)

    # Composición del capital (cap_circ = circulación, cap_cart = cartera).
    cap_circ_cantidad: int | None = None
    cap_circ_tipo: str | None = Field(default=None, max_length=40)
    cap_circ_votos: int | None = None
    cap_circ_suscripto: float | None = None
    cap_circ_integrado: float | None = None
    cap_cart_cantidad: int | None = None
    cap_cart_tipo: str | None = Field(default=None, max_length=40)
    cap_cart_votos: int | None = None
    cap_cart_suscripto: float | None = None
    cap_cart_integrado: float | None = None

    @field_validator(
        "duracion_entidad",
        "cap_circ_cantidad", "cap_circ_votos",
        "cap_circ_suscripto", "cap_circ_integrado",
        "cap_cart_cantidad", "cap_cart_votos",
        "cap_cart_suscripto", "cap_cart_integrado",
        mode="before",
    )
    @classmethod
    def _numeros_opcionales(cls, valor):
        """Los inputs numéricos vienen vacíos ("") o con coma decimal."""
        if valor is None or valor == "":
            return None
        if isinstance(valor, str):
            valor = valor.strip()
            if not valor:
                return None
            return float(valor.replace(",", "."))
        return valor


class ValorIn(BaseModel):
    seccion: str = Field(pattern="^(esp|er|eepn)$")
    clave: str = Field(min_length=1, max_length=60)
    valor_actual: float = 0
    valor_anterior: float = 0


class NotaIn(BaseModel):
    """Texto de una nota (clave del modelo: "1.1", "2.9", "7", …)."""

    clave: str = Field(min_length=1, max_length=10)
    texto: str = Field(default="", max_length=50000)


class CeldaNotaIn(BaseModel):
    """Importe de un cuadro de composición: clave "<nota>:<fila>:<columna>"."""

    clave: str = Field(min_length=3, max_length=30)
    valor: float = 0


class CuadrosRecalcular(BaseModel):
    """Sumatorias de los cuadros con estos importes, sin guardar nada."""

    celdas_nota: list[CeldaNotaIn] = Field(default_factory=list)


class BalanceGuardar(BaseModel):
    cabecera: CabeceraActualizar
    valores: list[ValorIn] = Field(default_factory=list)
    notas: list[NotaIn] | None = None
    celdas_nota: list[CeldaNotaIn] | None = None
