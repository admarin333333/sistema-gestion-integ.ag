from datetime import date, datetime
from decimal import Decimal

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

# Solo las notas de CRÉDITO. Son las que restan lo que el cliente debe: la nota
# de débito hace lo contrario (aumenta lo que debe), así que va aparte.
TIPOS_NOTA_CREDITO = ("nota_credito_a", "nota_credito_b", "nota_credito_c")

# pendiente · parcial · pagada lo recalcula el backend con SUM cuando se
# aplican recibos. "anulada" la pone únicamente el admin.
ESTADOS = ("pendiente", "parcial", "pagada", "anulada")


class Factura(Base):
    __tablename__ = "facturas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id"), nullable=False, index=True
    )
    # Si esta factura es una NOTA (de crédito o de débito), la factura a la que
    # corrige. Va en la misma tabla con una FK a sí misma.
    #
    # Por qué: una nota de crédito sin saber a qué factura se descuenta es un
    # papel suelto. El contador necesita saber si el cliente ya pagó lo que se
    # le está descontando, y eso solo se responde mirando la factura original.
    factura_relacionada_id: Mapped[int | None] = mapped_column(
        ForeignKey("facturas.id", name="fk_factura_relacionada"), nullable=True
    )

    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    tipo_comprobante: Mapped[str] = mapped_column(
        Enum(*TIPOS_COMPROBANTE, name="tipo_comprobante"), nullable=False
    )
    punto_venta: Mapped[str] = mapped_column(String(4), nullable=False)
    numero: Mapped[str] = mapped_column(String(8), nullable=False)
    concepto: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Total facturado. **No se toca**: sigue siendo el importe que usan los
    # recibos, el estado de cuenta y los informes.
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

    # --- Para el asiento contable automático -------------------------
    # Qué cuenta de ingresos va en el Haber: ventas de artículos (4.1) o
    # ingresos por servicios (4.2).
    tipo_operacion: Mapped[str] = mapped_column(
        String(12), nullable=False, default="SERVICIOS"
    )

    # Desglose del IVA. La regla es `importe = neto + iva`. Si vienen los dos en
    # NULL, el asiento va con el importe entero a ingresos y avisa.
    neto: Mapped[Decimal | None] = mapped_column(Numeric(16, 4), nullable=True)
    iva: Mapped[Decimal | None] = mapped_column(Numeric(16, 4), nullable=True)
    alicuota_iva_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # La alícuota que se aplicó (21.00), aunque después cambie la tabla.
    alicuota_iva_aplicada: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 2), nullable=True
    )

    # --- Libro de IVA Ventas (ver `migrar_iva_ventas.py`) ---
    #
    # Los dos campos que el libro necesita como columna y que en `compras` ya
    # existían pero en ventas no. En NULL = no aplica: una venta normal tiene
    # ambos en 0, no en NULL.
    #
    # `percepcion`: el IVA que el cliente le RETIENE al contador (3% en
    # honorarios de abogados, por ejemplo). Es plata que entra menos, y el
    # Libro de IVA Ventas la muestra en su propia columna.
    #
    # `no_gravado`: la parte del total que paga 0% o está exenta (exportaciones,
    # por ejemplo). Va aparte del neto porque también es ingreso sin IVA.
    percepcion: Mapped[Decimal | None] = mapped_column(Numeric(16, 4), nullable=True)
    no_gravado: Mapped[Decimal | None] = mapped_column(Numeric(16, 4), nullable=True)

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
