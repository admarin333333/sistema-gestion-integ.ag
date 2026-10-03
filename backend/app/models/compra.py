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
from app.models.factura import TIPOS_COMPROBANTE

ESTADOS_COMPRA = ("pendiente", "anulada")


class Compra(Base):
    """Factura de proveedor: neto + IVA (calculado) + percepción = total."""

    __tablename__ = "compras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # El proveedor es una fila de `proveedores` (que a su vez apunta a
    # `personas`), NO de `clientes`. Estuvo apuntando a `clientes` y por eso
    # cargar una compra siempre fallaba: la validación buscaba un `.tipo` que la
    # tabla de clientes no tiene. `Proveedor.__getattr__` delega en la persona,
    # así que `compra.proveedor.nombre_completo` sigue funcionando igual.
    proveedor_id: Mapped[int] = mapped_column(
        ForeignKey("proveedores.id"), nullable=False, index=True
    )

    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    tipo_comprobante: Mapped[str] = mapped_column(
        Enum(*TIPOS_COMPROBANTE, name="tipo_comprobante_compra"), nullable=False
    )
    punto_venta: Mapped[str] = mapped_column(String(4), nullable=False)
    numero: Mapped[str] = mapped_column(String(8), nullable=False)
    concepto: Mapped[str | None] = mapped_column(String(200), nullable=True)

    neto: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    alicuota_iva_id: Mapped[int] = mapped_column(
        ForeignKey("alicuotas_iva.id"), nullable=False, index=True
    )
    iva: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    percepcion_iva: Mapped[float] = mapped_column(
        Numeric(14, 2), nullable=False, default=0
    )
    total: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)

    # La cuenta del plan que se DEBITA en el asiento (6.1.03 luz-agua,
    # 6.2.01 publicidad...). El centro de costos sale de acá: 6.1 es
    # Administración, 6.2 es Comercialización. Es lo único que decide dónde
    # cae el gasto, así que el informe por centro nunca puede contradecir al
    # plan de cuentas.
    cuenta_gasto_id: Mapped[int | None] = mapped_column(
        ForeignKey("plan_cuentas.id_cuenta", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )

    # `centro_costo_id` y `tipo_gasto_id` quedaron SIN USO: eran una lista
    # paralela de centros y tipos de gasto que ya se contradecía con el plan
    # (Intereses estaba en Administración cuando en el plan es Financiero).
    # No se borraron las columnas ni los datos: es solo información vieja, y
    # dejarla no cuesta nada. Nullable porque el INSERT nuevo no los manda.
    centro_costo_id: Mapped[int | None] = mapped_column(
        ForeignKey("centros_costos.id"), nullable=True, index=True
    )
    tipo_gasto_id: Mapped[int | None] = mapped_column(
        ForeignKey("tipos_gasto.id"), nullable=True, index=True
    )

    fecha_vencimiento: Mapped[date | None] = mapped_column(Date, nullable=True)
    estado: Mapped[str] = mapped_column(
        Enum(*ESTADOS_COMPRA, name="estado_compra"),
        nullable=False,
        default="pendiente",
    )

    creado: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    actualizado: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    proveedor = relationship("Proveedor")
    alicuota = relationship("AlicuotaIva", lazy="selectin")
    cuenta_gasto = relationship("PlanCuenta", lazy="selectin")
    centro = relationship("CentroCosto", lazy="selectin")
    tipo_gasto = relationship("TipoGasto", lazy="selectin")

    @property
    def centro_nombre(self) -> str:
        """El centro de costos, derivado de la cuenta de gasto.

        No se elige: sale de la cuenta. Si elegís `6.2.01 publicidad`, el centro
        es `6.2 Gastos de comercialización`. Es lo que hace que el informe por
        centro y el asiento no puedan decir cosas distintas.

        Se sube por `padre` hasta llegar a la cuenta cuyo padre es la raíz de
        gastos (la 6). Si algún día el plan tiene un gasto más profundo
        (6.1.01.01), sigue funcionando: la búsqueda es por el vínculo, no por
        la cantidad de puntos del código.
        """
        cuenta = self.cuenta_gasto
        if cuenta is None:
            return ""
        while cuenta.padre is not None:
            if cuenta.padre.cuenta_padre_id is None:
                break  # `cuenta` cuelga de una raíz (la 6): es un centro
            cuenta = cuenta.padre
        return cuenta.nombre

    __table_args__ = (
        UniqueConstraint(
            "proveedor_id",
            "tipo_comprobante",
            "punto_venta",
            "numero",
            name="uq_compra_numero",
        ),
    )

    @property
    def proveedor_nombre(self) -> str:
        return self.proveedor.nombre_completo if self.proveedor else ""
