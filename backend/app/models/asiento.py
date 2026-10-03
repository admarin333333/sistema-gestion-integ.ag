from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.comprobante_interno import ComprobanteInterno
from app.models.plan_cuenta import PlanCuenta

# BORRADOR: se puede editar y no suma a los saldos.
# CONTABILIZADO: ya suma a los saldos y no se toca más.
# ANULADO: queda fuera de los saldos (para dar de baja sin borrar).
ESTADOS_ASIENTO = ("BORRADOR", "CONTABILIZADO", "ANULADO")

# Tipos de auxiliar que ya contempla el plan de cuentas.
TIPOS_AUXILIAR_DETALLE = ("CLIENTE", "PROVEEDOR", "BANCO")


class Asiento(Base):
    """Un asiento contable: el movimiento doble, Debe = Haber.

    `total_debe` y `total_haber` son el **control del asiento**, no el saldo de
    una cuenta: los calcula el sistema al guardar el detalle. El saldo de cada
    cuenta nunca se guarda, se calcula con SQL sobre lo contabilizado.
    """

    __tablename__ = "asientos"

    id_asiento: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )

    # NULL: se puede hacer un asiento sin comprobante (un ajuste interno).
    id_comprobante: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "comprobantes_internos.id_comprobante",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=True,
        index=True,
    )

    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    concepto: Mapped[str] = mapped_column(String(200), nullable=False)
    estado: Mapped[str] = mapped_column(
        String(15), nullable=False, default="BORRADOR"
    )

    total_debe: Mapped[Decimal] = mapped_column(
        Numeric(16, 4), nullable=False, default=Decimal("0")
    )
    total_haber: Mapped[Decimal] = mapped_column(
        Numeric(16, 4), nullable=False, default=Decimal("0")
    )

    # La diferencia (total_debe - total_haber). Se calcula al vuelo, no se
    # guarda: si el detalle cambia, cambia sola.
    @property
    def diferencia(self) -> Decimal:
        return (self.total_debe or Decimal("0")) - (self.total_haber or Decimal("0"))

    @property
    def balanceado(self) -> bool:
        return self.diferencia == Decimal("0")

    comprobante: Mapped["ComprobanteInterno | None"] = relationship(
        "ComprobanteInterno", back_populates="asientos"
    )
    detalle: Mapped[list["AsientoDetalle"]] = relationship(
        "AsientoDetalle",
        back_populates="asiento",
        cascade="all, delete-orphan",
        order_by="AsientoDetalle.id_detalle",
    )

    creado: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    actualizado: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - solo para depurar
        return f"<Asiento {self.id_asiento} {self.estado}>"


class AsientoDetalle(Base):
    """Una línea del asiento: cuánto entra en una cuenta por el Debe y el Haber.

    Solo se admiten cuentas **imputables** del plan de cuentas: un agrupador no
    puede recibir un movimiento.

    Los auxiliares van en dos columnas (`tipo_auxiliar` + `id_auxiliar`) y hoy
    están en NULL: quedan listas para cuando hagan falta.
    """

    __tablename__ = "asiento_detalle"

    id_detalle: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    id_asiento: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("asientos.id_asiento", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    id_cuenta: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "plan_cuentas.id_cuenta", ondelete="RESTRICT", onupdate="CASCADE"
        ),
        nullable=False,
        index=True,
    )

    # 4 decimales, como el resto del sistema (índices y coeficientes).
    debe: Mapped[Decimal] = mapped_column(
        Numeric(16, 4), nullable=False, default=Decimal("0")
    )
    haber: Mapped[Decimal] = mapped_column(
        Numeric(16, 4), nullable=False, default=Decimal("0")
    )

    tipo_auxiliar: Mapped[str | None] = mapped_column(String(30), nullable=True)
    id_auxiliar: Mapped[int | None] = mapped_column(Integer, nullable=True)

    asiento: Mapped["Asiento"] = relationship("Asiento", back_populates="detalle")
    cuenta: Mapped["PlanCuenta"] = relationship("PlanCuenta")

    @property
    def importe(self) -> Decimal:
        """Saldo de la línea: en una cuenta deudora es Debe − Haber."""
        return (self.debe or Decimal("0")) - (self.haber or Decimal("0"))

    def __repr__(self) -> str:  # pragma: no cover - solo para depurar
        return f"<AsientoDetalle cuenta={self.id_cuenta} debe={self.debe} haber={self.haber}>"