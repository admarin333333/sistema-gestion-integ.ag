from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class ClienteListadoOut(BaseModel):
    """Lo que devuelve el listado y la ficha: datos de la persona + lo del módulo."""

    id: int  # id de la fila del módulo (clientes), no el de la persona
    persona_id: int
    tipo: str = "cliente"
    nro_cuenta: int

    tipo_persona: str
    nombre: str
    apellido: Optional[str] = None
    cuit: Optional[str] = None
    # Si el CUIT no cierra el dígito verificador, sale el texto del aviso.
    # No bloquea nada: solo informa.
    cuit_advertencia: Optional[str] = None
    dni: Optional[str] = None
    clave_fiscal: Optional[str] = None
    fecha_carga_clave_fiscal: Optional[date] = None
    fecha_modif_clave_fiscal: Optional[datetime] = None
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
    alicuota_iva: Optional[dict] = None
    observaciones: Optional[str] = None
    fecha_cierre_ejercicio: Optional[date] = None
    presenta_eecc: bool = True
    fecha_alta: date
    creado: datetime
    actualizado: Optional[datetime] = None

    nombre_completo: str
    servicios: list = []
    sugerencias: list = []