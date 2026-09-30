from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.sugerencia import Sugerencia

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


class Cliente(Base):
    __tablename__ = "clientes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # --- persona ---
    tipo_persona: Mapped[str] = mapped_column(
        Enum(*TIPOS_PERSONA, name="tipo_persona"), nullable=False
    )
    # persona física: nombre + apellido | persona jurídica: nombre = razón social
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    apellido: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cuit: Mapped[str | None] = mapped_column(
        String(13), unique=True, nullable=True, index=True
    )
    dni: Mapped[str | None] = mapped_column(
        String(10), unique=True, nullable=True, index=True
    )

    # --- contacto ---
    email: Mapped[str | None] = mapped_column(String(120), nullable=True)
    cod_area: Mapped[str | None] = mapped_column(String(5), nullable=True)
    telefono: Mapped[str | None] = mapped_column(String(20), nullable=True)
    domicilio: Mapped[str | None] = mapped_column(String(150), nullable=True)
    localidad: Mapped[str | None] = mapped_column(String(100), nullable=True)
    codigo_postal: Mapped[str | None] = mapped_column(String(4), nullable=True)
    provincia: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # --- actividad ---
    actividad_economica: Mapped[str] = mapped_column(
        Enum(*ACTIVIDADES_ECONOMICAS, name="actividad_economica"), nullable=False
    )
    tipo_actividad: Mapped[str] = mapped_column(
        Enum(*TIPOS_ACTIVIDAD, name="tipo_actividad"), nullable=False
    )

    observaciones: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha_alta: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    creado: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    actualizado: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    servicios: Mapped[list["Servicio"]] = relationship(  # noqa: F821
        secondary="cliente_servicio",
        back_populates="clientes",
        lazy="selectin",
    )
    sugerencias: Mapped[list[Sugerencia]] = relationship(
        back_populates="cliente",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="Sugerencia.fecha.desc()",
    )

    @property
    def nombre_completo(self) -> str:
        """Cómo se muestra el cliente en los listados."""
        if self.tipo_persona == "juridica":
            return self.nombre
        if self.apellido:
            return f"{self.apellido}, {self.nombre}"
        return self.nombre
