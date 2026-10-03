from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from app.models.asiento import TIPOS_AUXILIAR_DETALLE


# ----------------------------------------------------------------- comprobante

class ComprobanteInternoOut(BaseModel):
    id_comprobante: int
    codigo_comprobante: str
    anio: int
    numero: int
    fecha: date
    concepto: str
    estado: str
    # Como se ve: OP-000125
    numero_completo: str = ""
    # A qué ejercicio del estudio pertenece. La numeración corre POR EJERCICIO,
    # no por año: por eso dos comprobantes de años distintos pueden ser 000001.
    id_ejercicio: Optional[int] = None


class ComprobanteInternoCrear(BaseModel):
    codigo_comprobante: str = Field(..., min_length=1, max_length=10)
    fecha: date
    concepto: str = Field(..., min_length=1, max_length=200)


# --------------------------------------------------------------------- asiento

class DetalleIn(BaseModel):
    """Una línea del asiento, tal como la manda el navegador."""

    id_cuenta: int = Field(..., gt=0)
    debe: Decimal = Decimal("0")
    haber: Decimal = Decimal("0")
    # Todavía en NULL: queda armado para cuando se usen los auxiliares.
    tipo_auxiliar: Optional[str] = None
    id_auxiliar: Optional[int] = None


class DetalleOut(BaseModel):
    id_detalle: int
    id_cuenta: int
    codigo: str = ""
    nombre_cuenta: str = ""
    deudora_acreadora: Optional[str] = None
    debe: Decimal
    haber: Decimal
    tipo_auxiliar: Optional[str] = None
    id_auxiliar: Optional[int] = None
    # El nombre del cliente al que pertenece el movimiento. Sin esto, en la
    # pantalla del recibo se lee "Documentos a cobrar 1.000,00" y no se sabe de
    # quién es. Los endpoints que declaran `response_model` cortan las claves
    # que no estén acá, así que tiene que estar en el schema sí o sí.
    auxiliar_nombre: Optional[str] = None


class AsientoCrear(BaseModel):
    fecha: date
    concepto: str = Field(..., min_length=1, max_length=200)
    id_comprobante: Optional[int] = None
    # Si no se pasa comprobante ya creado, se crea uno con este código y
    # queda numerado solo. Por defecto "AB" (asiento en blanco, manual).
    codigo_comprobante: str = Field(default="AB", max_length=10)


class AsientoDetalleIn(BaseModel):
    """Reemplaza todas las líneas del asiento de una sola vez."""

    detalle: list[DetalleIn] = Field(default_factory=list)


class AsientoOut(BaseModel):
    id_asiento: int
    id_comprobante: Optional[int] = None
    numero_completo: Optional[str] = None
    fecha: date
    concepto: str
    estado: str
    total_debe: Decimal
    total_haber: Decimal
    # Se calcula al vuelo: total_debe - total_haber.
    diferencia: Decimal = Decimal("0")
    balanceado: bool = False
    detalle: list[DetalleOut] = Field(default_factory=list)


# -------------------------------------------------------------- plan de cuentas

class BusquedaCuentaOut(BaseModel):
    """Una cuenta del plan, para el buscador de líneas del asiento.

    Solo se devuelven las **imputables**: una agrupadora no recibe movimientos,
    así que no tiene sentido ofrecerla.
    """

    id_cuenta: int
    codigo: str
    nombre: str
    nivel: int
    deudora_acreadora: Optional[str] = None
    tipo_auxiliar: Optional[str] = None


# --------------------------------------------------------------------- saldos

class SaldoOut(BaseModel):
    id_cuenta: int
    codigo: str
    nombre: str
    nivel: int
    naturaleza: str
    deudora_acreadora: Optional[str] = None
    total_debe: Decimal
    total_haber: Decimal
    """Saldo con el signo de la naturaleza: en una deudora es Debe − Haber,
    en una acreedora es Haber − Debe. Positivo = a favor."""
    saldo: Decimal
    movimientos: int


class ControlGeneralOut(BaseModel):
    """Que todo asiento contabilizado tenga Debe = Haber."""

    asientos_contabilizados: int
    total_debe: str
    total_haber: str
    diferencia_general: str
    ok: bool
    problemas: list[dict] = Field(default_factory=list)