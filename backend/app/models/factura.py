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

# Tipos de comprobante. La numeración es MANUAL: este sistema todavía no
# habla con ARCA, así que el CAE se deja vacío hasta la Fase 6.
TIPOS_COMPROBANTE = (
    "factura_a",
    "factura_b",
    "factura_c",
    "nota_credito_a",
    "nota_credito_b",
    "nota_credito_c",
    "nota_debito_a",
    "nota_debito_b",
    "nota_debito_c",
)

CONDICIONES_VENTA = ("contado", "cta_corriente_15", "cta_corriente_30")

# pendiente · parcial · pagada lo recalcula el backend con SUM cuando se
# aplican recibos. "anulada" la pone únicamente el admin.
ESTADOS = ("pendiente", "parcial", "pagada", "anulada")


class Factura(Base):
    __tablename__ = "facturas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id"), nullable=False, index=True
    )

    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    tipo_comprobante: Mapped[str] = mapped_column(
        Enum(*TIPOS_COMPROBANTE, name="tipo_comprobante"), nullable=False
    )
    punto_venta: Mapped[str] = mapped_column(String(4), nullable=False)
    numero: Mapped[str] = mapped_column(String(8), nullable=False)
    concepto: Mapped[str | None] = mapped_column(String(200), nullable=True)
    importe: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    fecha_vencimiento: Mapped[date | None] = mapped_column(Date, nullable=True)
    condicion_venta: Mapped[str] = mapped_column(
        Enum(*CONDICIONES_VENTA, name="condicion_venta"),
        nullable=False,
        default="contado",
    )
    estado: Mapped[str] = mapped_column(
        Enum(*ESTADOS, name="estado_factura"), nullable=False, default="pendiente"
    )

    # ARCA: opcionales. Hoy se cargan a mano si se tienen.
    cae: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cae_vencimiento: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Última vez que se envió por mail al cliente (NULL = nunca se mandó)
    fecha_envio: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    creado: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    actualizado: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    cliente = relationship("Cliente")

    __table_args__ = (
        UniqueConstraint(
            "tipo_comprobante",
            "punto_venta",
            "numero",
            name="uq_factura_numero",
        ),
    )

    @property
    def cliente_nombre(self) -> str:
        return self.cliente.nombre_completo if self.cliente else ""
