import re
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.cliente import ACTIVIDADES_ECONOMICAS, TIPOS_ACTIVIDAD, TIPOS_PERSONA
from app.schemas.servicio import ServicioOut
from app.schemas.sugerencia import SugerenciaOut

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")


def _limpiar_digitos(valor: str) -> str:
    return valor.replace("-", "").replace(".", "").replace(" ", "")


class ClienteBase(BaseModel):
    tipo_persona: str
    nombre: str = Field(min_length=2, max_length=100)
    apellido: str | None = Field(default=None, max_length=100)
    cuit: str | None = Field(default=None, max_length=13)
    dni: str | None = Field(default=None, max_length=10)
    email: str | None = Field(default=None, max_length=120)
    cod_area: str | None = Field(default=None)
    telefono: str | None = Field(default=None, max_length=20)
    domicilio: str | None = Field(default=None, max_length=150)
    localidad: str | None = Field(default=None, max_length=100)
    codigo_postal: str | None = Field(default=None)
    provincia: str | None = Field(default=None, max_length=100)
    actividad_economica: str
    tipo_actividad: str
    observaciones: str | None = None
    servicios: list[int] = Field(default_factory=list)

    @field_validator("tipo_persona")
    @classmethod
    def _persona(cls, valor: str) -> str:
        if valor not in TIPOS_PERSONA:
            raise ValueError(f"Tipo de persona inválido ({', '.join(TIPOS_PERSONA)})")
        return valor

    @field_validator("actividad_economica")
    @classmethod
    def _actividad(cls, valor: str) -> str:
        if valor not in ACTIVIDADES_ECONOMICAS:
            raise ValueError("Actividad económica inválida")
        return valor

    @field_validator("tipo_actividad")
    @classmethod
    def _tipo_actividad(cls, valor: str) -> str:
        if valor not in TIPOS_ACTIVIDAD:
            raise ValueError("Tipo de actividad inválido")
        return valor

    @field_validator("nombre", "apellido", "domicilio", "localidad", "provincia")
    @classmethod
    def _sin_vacio(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        limpio = valor.strip()
        return limpio or None

    @field_validator("cuit")
    @classmethod
    def _validar_cuit(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        digitos = _limpiar_digitos(valor)
        if not digitos.isdigit() or len(digitos) != 11:
            raise ValueError("El CUIT debe tener 11 dígitos (formato XX-XXXXXXXX-X)")
        return f"{digitos[:2]}-{digitos[2:10]}-{digitos[10]}"

    @field_validator("dni")
    @classmethod
    def _validar_dni(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        digitos = _limpiar_digitos(valor)
        if not digitos.isdigit() or not 7 <= len(digitos) <= 8:
            raise ValueError("El DNI debe tener 7 u 8 dígitos, solo números")
        return digitos

    @field_validator("email")
    @classmethod
    def _validar_email(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        limpio = valor.strip()
        if not limpio:
            return None
        if not _EMAIL.match(limpio):
            raise ValueError("El email no tiene un formato válido")
        return limpio

    @field_validator("codigo_postal")
    @classmethod
    def _validar_codigo_postal(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        digitos = _limpiar_digitos(valor)
        if not digitos:
            return None
        if not digitos.isdigit() or len(digitos) != 4:
            raise ValueError("El código postal tiene 4 dígitos (ej.: 5854)")
        return digitos

    @field_validator("cod_area")
    @classmethod
    def _validar_cod_area(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        digitos = _limpiar_digitos(valor)
        if not digitos:
            return None
        if not digitos.isdigit() or not 2 <= len(digitos) <= 5:
            raise ValueError("El código de área tiene de 2 a 5 dígitos (ej.: 351)")
        return digitos

    @field_validator("telefono")
    @classmethod
    def _validar_telefono(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        digitos = _limpiar_digitos(valor)
        if not digitos:
            return None
        if not digitos.isdigit() or not 4 <= len(digitos) <= 11:
            raise ValueError("El teléfono tiene de 4 a 11 dígitos, solo números")
        return digitos

    @model_validator(mode="after")
    def _coherencia(self) -> "ClienteBase":
        if self.tipo_persona == "fisica":
            if not self.apellido:
                raise ValueError("En persona física el apellido es obligatorio")
            if not self.dni:
                raise ValueError("En persona física el DNI es obligatorio")
        else:  # juridica
            if not self.cuit:
                raise ValueError("En persona jurídica el CUIT es obligatorio")
            if self.dni:
                raise ValueError("La persona jurídica no tiene DNI")
        return self


class ClienteCrear(ClienteBase):
    pass


class ClienteActualizar(ClienteBase):
    pass


class ClienteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tipo_persona: str
    nombre: str
    apellido: str | None = None
    nombre_completo: str
    cuit: str | None = None
    dni: str | None = None
    email: str | None = None
    cod_area: str | None = None
    telefono: str | None = None
    domicilio: str | None = None
    localidad: str | None = None
    codigo_postal: str | None = None
    provincia: str | None = None
    actividad_economica: str
    tipo_actividad: str
    observaciones: str | None = None
    fecha_alta: date
    creado: datetime
    actualizado: datetime | None = None
    servicios: list[ServicioOut] = Field(default_factory=list)
    sugerencias: list[SugerenciaOut] = Field(default_factory=list)
