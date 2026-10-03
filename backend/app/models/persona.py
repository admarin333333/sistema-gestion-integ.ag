from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

TIPOS_PERSONA = ("fisica", "juridica")

CONDICIONES_IVA = (
    "consumidor_final",
    "monotributista",
    "responsable_inscripto",
)

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


class Persona(Base):
    """Datos comunes de toda persona (física o jurídica) del sistema."""

    __tablename__ = "personas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # --- persona ---
    tipo_persona: Mapped[str] = mapped_column(
        Enum(*TIPOS_PERSONA, name="tipo_persona"), nullable=False
    )
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    apellido: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cuit: Mapped[str | None] = mapped_column(String(13), nullable=True, index=True)
    dni: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)

    # --- clave fiscal de ARCA ---
    # Sirve para trabajar en ARCA en nombre del contribuyente. Es opcional
    # (no todos los clientes la tienen: p.ej. los que entran con su CUIT).
    clave_fiscal: Mapped[str | None] = mapped_column(String(11), nullable=True)
    fecha_carga_clave_fiscal: Mapped[date | None] = mapped_column(Date, nullable=True)
    fecha_modif_clave_fiscal: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )

    # --- contacto ---
    email: Mapped[str | None] = mapped_column(String(120), nullable=True)
    cod_area: Mapped[str | None] = mapped_column(String(5), nullable=True)
    telefono: Mapped[str | None] = mapped_column(String(20), nullable=True)
    calle: Mapped[str | None] = mapped_column(String(30), nullable=True)
    numero_calle: Mapped[str | None] = mapped_column(String(10), nullable=True)
    localidad: Mapped[str | None] = mapped_column("locality", String(100), nullable=True)
    codigo_postal: Mapped[str | None] = mapped_column(String(4), nullable=True)
    provincia: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # --- actividad ---
    actividad_economica: Mapped[str] = mapped_column(
        Enum(*ACTIVIDADES_ECONOMICAS, name="actividad_economica"), nullable=False
    )
    tipo_actividad: Mapped[str] = mapped_column(
        Enum(*TIPOS_ACTIVIDAD, name="tipo_actividad"), nullable=False
    )

    # --- iva ---
    condicion_iva: Mapped[str] = mapped_column(
        Enum(*CONDICIONES_IVA, name="condicion_iva"), nullable=False
    )
    alicuota_iva_id: Mapped[int | None] = mapped_column(
        ForeignKey("alicuotas_iva.id"), nullable=True, index=True
    )

    observaciones: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha_cierre_ejercicio: Mapped[date | None] = mapped_column(Date, nullable=True)
    presenta_eecc: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    fecha_alta: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    creado: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    actualizado: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # --- relaciones ---
    alicuota_iva: Mapped["AlicuotaIva | None"] = relationship(  # noqa: F821
        lazy="selectin",
    )
    cliente: Mapped["Cliente | None"] = relationship(  # noqa: F821
        back_populates="persona",
        uselist=False,
    )
    proveedor: Mapped["Proveedor | None"] = relationship(  # noqa: F821
        back_populates="persona",
        uselist=False,
    )

    __table_args__ = (
        UniqueConstraint("cuit", name="uq_persona_cuit"),
        UniqueConstraint("dni", name="uq_persona_dni"),
    )

    @property
    def nombre_completo(self) -> str:
        """Cómo se muestra la persona en los listados."""
        if self.tipo_persona == "juridica":
            return self.nombre
        if self.apellido:
            return f"{self.apellido}, {self.nombre}"
        return self.nombre

    @property
    def domicilio(self) -> str:
        """Dirección completa para informes (ej.: 'Av. Siempreviva 742')."""
        return " ".join(p for p in (self.calle, self.numero_calle) if p)