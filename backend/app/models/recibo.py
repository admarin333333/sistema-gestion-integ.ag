from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

FORMAS_PAGO = (
    "transferencia",
    "efectivo",
    "tarjeta_credito",
    "tarjeta_debito",
    "cheque",
    "otro",
)


class Recibo(Base):
    __tablename__ = "recibos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id"), nullable=False, index=True
    )

    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    numero: Mapped[str] = mapped_column(String(8), nullable=False, unique=True)
    importe: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    forma_pago: Mapped[str] = mapped_column(
        Enum(*FORMAS_PAGO, name="forma_pago"), nullable=False
    )

    creado: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    actualizado: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    cliente = relationship("Cliente")
    aplicaciones: Mapped[list["Aplicacion"]] = relationship(  # noqa: F821
        back_populates="recibo", cascade="all, delete-orphan"
    )

    @property
    def cliente_nombre(self) -> str:
        return self.cliente.nombre_completo if self.cliente else ""


class Aplicacion(Base):
    """Un recibo puede repartirse entre varias facturas: cada fila es
    cuánto de ese recibo se destinó a una factura."""

    __tablename__ = "aplicaciones_recibo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recibo_id: Mapped[int] = mapped_column(
        ForeignKey("recibos.id"), nullable=False, index=True
    )
    factura_id: Mapped[int] = mapped_column(
        ForeignKey("facturas.id"), nullable=False, index=True
    )
    importe: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    creado: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    recibo = relationship("Recibo", back_populates="aplicaciones")
    factura = relationship("Factura")

    __table_args__ = (UniqueConstraint("recibo_id", "factura_id", name="uq_aplicacion"),)
