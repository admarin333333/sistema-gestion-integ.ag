"""Schemas de persona (datos comunes a clientes y proveedores).

Las validaciones viven **acá en el backend**, no solo en el formulario: el
espejo (Fase 6) y las pruebas llaman la API directo, y si el backend acepta
cualquier cosa quedan datos sucios que después hay que reparar a mano.
Ver MEMORIA §4.2.
"""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

TIPOS_PERSONA = ("fisica", "juridica")
ACTIVIDADES_ECONOMICAS = (
    "profesional",
    "comercio",
    "industria",
    "cabanas",
    "inmobiliaria",
    "servicios",
)
TIPOS_ACTIVIDAD = (
    "monotributista",
    "responsable_inscripto",
    "autonomo",
    "cooperativa",
    "asociacion_civil",
)
CONDICIONES_IVA = (
    "consumidor_final",
    "monotributista",
    "responsable_inscripto",
)


def _sin_guiones(valor: str) -> str:
    return "".join(c for c in valor if c.isdigit())


# Multiplicadores del dígito verificador del CUIT/CUIL (módulo 11, norma ARCA).
_PESOS_CUIT = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)


def digito_verificador_cuit(diez_digitos: str) -> int | None:
    """Calcula el dígito verificador de un CUIT (módulo 11, norma ARCA).

    Recibe los primeros 10 dígitos. Devuelve el dígito, o `None` si el resto
    da 1 (esa combinación no existe para CUIT: solo aparece en CUIL).
    """
    suma = sum(int(d) * p for d, p in zip(diez_digitos, _PESOS_CUIT))
    resto = suma % 11
    if resto == 0:
        return 0
    if resto == 1:
        return None  # no hay CUIT válido con este resto
    return 11 - resto


def cuit_es_valido(valor: str) -> bool:
    """¿El CUIT existe de verdad? (11 dígitos + prefijo + dígito verificador)."""
    digitos = _sin_guiones(valor)
    if len(digitos) != 11 or not digitos.isdigit():
        return False
    if digitos[:2] not in ("20", "23", "24", "27", "30", "33", "34"):
        return False
    esperado = digito_verificador_cuit(digitos[:10])
    return esperado is not None and esperado == int(digitos[10])


def _normalizar_cuit(valor: Optional[str]) -> Optional[str]:
    """'20264736742' -> '20-26473674-2' (así el mismo CUIT no se duplica)."""
    if valor is None:
        return None
    v = valor.strip()
    if not v:
        return None
    d = _sin_guiones(v)
    if len(d) != 11:
        return v  # se devuelve tal cual; `_chequear_cuit` lo va a rechazar
    return f"{d[:2]}-{d[2:10]}-{d[10]}"


def _chequear_cuit(valor: Optional[str]) -> None:
    """CUIT: 11 dígitos con el formato XX-NNNNNNNN-D."""
    if valor is None or valor.strip() == "":
        return
    digitos = _sin_guiones(valor)
    if len(digitos) != 11:
        raise ValueError(
            "el CUIT tiene que tener 11 dígitos (ej.: 20-26473675-8)"
        )
    if not valor.replace("-", "").isdigit():
        raise ValueError("el CUIT solo puede tener números y guiones")
    if digitos[:2] not in ("20", "23", "24", "27", "30", "33", "34"):
        raise ValueError("el CUIT tiene que empezar con 20, 23, 24, 27, 30, 33 o 34")
    # El dígito verificador (módulo 11) **no** bloquea el guardado: solo avisa.
    # Si lo bloqueara, un CUIT mal tipeado deja al cliente sin poder editar
    # NADA (ni el teléfono, ni una observación) hasta encontrar el error.
    # Ver `cuit_advertencia()`, que la ficha y el formulario muestran en amarillo.


def cuit_advertencia(valor: Optional[str]) -> Optional[str]:
    """Aviso sobre el CUIT, o None si está bien.

    El CUIT tiene un **dígito verificador** (módulo 11, norma ARCA) que avisa de
    los números tipeados al revés. Con 11 dígitos y prefijo válido todavía hay
    miles de combinaciones que no son CUITs reales, así que conviene avisar.
    No se bloquea el guardado: el contador contable (los estudios del estudio)
    puede tener CUITs raros y no queremos dejar al cliente trabado por eso.
    """
    if valor is None or valor.strip() == "":
        return None
    digitos = _sin_guiones(valor)
    if len(digitos) != 11 or not digitos.isdigit():
        return None  # esto sí lo rechaza el guardado
    if digitos[:2] not in ("20", "23", "24", "27", "30", "33", "34"):
        return None
    if cuit_es_valido(valor):
        return None
    verificador = digito_verificador_cuit(digitos[:10])
    if verificador is None:
        return (
            "Revisá el CUIT: con esos 10 dígitos no hay ningún dígito verificador "
            "posible, así que el número no existe."
        )
    return (
        f"Revisá el CUIT: el dígito verificador debería terminar en "
        f"{verificador} y no en {digitos[10]}."
    )


def _chequear_dni(valor: Optional[str]) -> None:
    """DNI: solo números (sin letras ni símbolos)."""
    if valor is None or valor.strip() == "":
        return
    if not valor.isdigit():
        raise ValueError("el DNI solo puede tener números")
    if not 6 <= len(valor) <= 10:
        raise ValueError("el DNI tiene que tener entre 6 y 10 dígitos")


def _chequear_email(valor: Optional[str]) -> None:
    if valor is None or valor.strip() == "":
        return
    if "@" not in valor or "." not in valor.split("@")[-1]:
        raise ValueError("el email no es válido (falta el @ o el dominio)")


def _chequear_codigo_postal(valor: Optional[str]) -> None:
    """Código postal: 4 dígitos."""
    if valor is None or valor.strip() == "":
        return
    if not valor.isdigit():
        raise ValueError("el código postal solo puede tener números")
    if len(valor) != 4:
        raise ValueError("el código postal tiene que tener 4 dígitos")


def _chequear_cod_area(valor: Optional[str]) -> None:
    """Código de área: 2 a 5 dígitos."""
    if valor is None or valor.strip() == "":
        return
    if not valor.isdigit():
        raise ValueError("el código de área solo puede tener números")
    if not 2 <= len(valor) <= 5:
        raise ValueError("el código de área tiene que tener entre 2 y 5 dígitos")


def _chequear_telefono(valor: Optional[str]) -> None:
    """Teléfono: 4 a 11 dígitos."""
    if valor is None or valor.strip() == "":
        return
    if not valor.isdigit():
        raise ValueError("el teléfono solo puede tener números")
    if not 4 <= len(valor) <= 11:
        raise ValueError("el teléfono tiene que tener entre 4 y 11 dígitos")


def _chequear_campos_comunes(datos: dict) -> None:
    """Las reglas que valen igual para todos los tipos de persona."""
    _chequear_cuit(datos.get("cuit"))
    _chequear_dni(datos.get("dni"))
    _chequear_email(datos.get("email"))
    _chequear_codigo_postal(datos.get("codigo_postal"))
    _chequear_cod_area(datos.get("cod_area"))
    _chequear_telefono(datos.get("telefono"))


def _chequear_persona(datos: dict) -> None:
    """Reglas que dependen de si es persona física o jurídica (MEMORIA §4.2)."""
    tipo = datos.get("tipo_persona")
    if tipo not in TIPOS_PERSONA:
        raise ValueError("el tipo de persona tiene que ser 'fisica' o 'juridica'")

    nombre = (datos.get("nombre") or "").strip()
    apellido = (datos.get("apellido") or "").strip()
    cuit = (datos.get("cuit") or "").strip()
    dni = (datos.get("dni") or "").strip()

    if not nombre:
        raise ValueError("el nombre es obligatorio")

    if tipo == "juridica":
        # En las jurídicas la razón social va en `nombre`; `apellido` va vacío.
        if not cuit:
            raise ValueError("el CUIT es obligatorio para personas jurídicas")
        if dni:
            raise ValueError("una persona jurídica no lleva DNI")
    else:
        if not apellido:
            raise ValueError("el apellido es obligatorio para personas físicas")
        if not dni:
            raise ValueError("el DNI es obligatorio para personas físicas")

    for campo, permitidos in (
        ("actividad_economica", ACTIVIDADES_ECONOMICAS),
        ("tipo_actividad", TIPOS_ACTIVIDAD),
        ("condicion_iva", CONDICIONES_IVA),
    ):
        valor = datos.get(campo)
        if valor is not None and valor not in permitidos:
            raise ValueError(f"el valor de {campo} no es válido: {valor}")


class PersonaBase(BaseModel):
    tipo_persona: str
    nombre: str
    apellido: Optional[str] = None
    cuit: Optional[str] = None
    dni: Optional[str] = None
    clave_fiscal: Optional[str] = None
    email: Optional[str] = None
    cod_area: Optional[str] = None
    telefono: Optional[str] = None
    calle: Optional[str] = None
    numero_calle: Optional[str] = None
    localidad: Optional[str] = None
    codigo_postal: Optional[str] = None
    provincia: Optional[str] = None
    actividad_economica: str
    tipo_actividad: str
    condicion_iva: str
    alicuota_iva_id: Optional[int] = None
    observaciones: Optional[str] = None
    fecha_cierre_ejercicio: Optional[date] = None
    presenta_eecc: bool = True

    @field_validator("cuit", mode="before")
    @classmethod
    def _normalizar(cls, valor):
        return _normalizar_cuit(valor)

    @model_validator(mode="after")
    def _validar(self):
        datos = self.model_dump()
        _chequear_campos_comunes(datos)
        _chequear_persona(datos)
        return self


class PersonaCreate(PersonaBase):
    pass


class PersonaUpdate(BaseModel):
    tipo_persona: Optional[str] = None
    nombre: Optional[str] = None
    apellido: Optional[str] = None
    cuit: Optional[str] = None
    dni: Optional[str] = None
    clave_fiscal: Optional[str] = None
    email: Optional[str] = None
    cod_area: Optional[str] = None
    telefono: Optional[str] = None
    calle: Optional[str] = None
    numero_calle: Optional[str] = None
    localidad: Optional[str] = None
    codigo_postal: Optional[str] = None
    provincia: Optional[str] = None
    actividad_economica: Optional[str] = None
    tipo_actividad: Optional[str] = None
    condicion_iva: Optional[str] = None
    alicuota_iva_id: Optional[int] = None
    observaciones: Optional[str] = None
    fecha_cierre_ejercicio: Optional[date] = None
    presenta_eecc: Optional[bool] = None

    @field_validator("cuit", mode="before")
    @classmethod
    def _normalizar(cls, valor):
        return _normalizar_cuit(valor)

    @model_validator(mode="after")
    def _validar(self):
        # Solo se miran los campos que vinieron en el pedido: un PUT parcial
        # (por ejemplo {email: ...}) no tiene por qué traer apellido ni DNI.
        enviados = self.model_dump(exclude_unset=True)
        _chequear_campos_comunes(enviados)
        if "tipo_persona" in enviados:
            if enviados["tipo_persona"] not in TIPOS_PERSONA:
                raise ValueError(
                    "el tipo de persona tiene que ser 'fisica' o 'juridica'"
                )
        for campo, permitidos in (
            ("actividad_economica", ACTIVIDADES_ECONOMICAS),
            ("tipo_actividad", TIPOS_ACTIVIDAD),
            ("condicion_iva", CONDICIONES_IVA),
        ):
            valor = enviados.get(campo)
            if valor is not None and valor not in permitidos:
                raise ValueError(f"el valor de {campo} no es válido: {valor}")
        return self


class PersonaOut(PersonaBase):
    id: int
    nombre_completo: str
    fecha_alta: date
    creado: datetime
    actualizado: Optional[datetime] = None
    # Clave fiscal: las fechas las calcula el backend, no las manda el usuario.
    fecha_carga_clave_fiscal: Optional[date] = None
    fecha_modif_clave_fiscal: Optional[datetime] = None

    model_config = {"from_attributes": True}