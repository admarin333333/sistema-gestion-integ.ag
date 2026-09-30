from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# estado: "disponible" hasta que se imputa; parcial/aplicado lo recalcula el
# backend con SUM cuando se le asignan facturas. "eliminado" no borra el
# registro: deja el movimiento contrario en el estado de cuenta.
ESTADOS_ANTICIPO = ("disponible", "parcial", "aplicado", "eliminado")


class Anticipo(Base):
    """Plata que el cliente adelantó ANTES de que se le facture."""

    __tablename__ = "anticipos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id"), nullable=False, index=True
    )

    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    numero: Mapped[str] = mapped_column(String(8), nullable=False, unique=True)
    importe: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    estado: Mapped[str] = mapped_column(
        Enum(*ESTADOS_ANTICIPO, name="estado_anticipo"),
        nullable=False,
        default="disponible",
    )

    creado: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    actualizado: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    cliente = relationship("Cliente")
    aplicaciones: Mapped[list["AplicacionAnticipo"]] = relationship(  # noqa: F821
        back_populates="anticipo", cascade="all, delete-orphan"
    )

    @property
    def cliente_nombre(self) -> str:
        return self.cliente.nombre_completo if self.cliente else ""


class AplicacionAnticipo(Base):
    """Cuánto de este anticipo se destinó a cada factura. NO mueve plata:
    la plata ya entró como HABER al alta; esto es solo la etiqueta de
    a qué factura se imputa (igual que las aplicaciones de recibo)."""

    __tablename__ = "aplicaciones_anticipo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    anticipo_id: Mapped[int] = mapped_column(
        ForeignKey("anticipos.id"), nullable=False, index=True
    )
    factura_id: Mapped[int] = mapped_column(
        ForeignKey("facturas.id"), nullable=False, index=True
    )
    importe: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    creado: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    anticipo = relationship("Anticipo", back_populates="aplicaciones")
    factura = relationship("Factura")
