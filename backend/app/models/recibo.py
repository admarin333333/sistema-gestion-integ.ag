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

ESTADOS_RECIBO = ("emitido", "anulado")


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
    # **En qué cuenta entró la plata** (Caja, Banco Nación, etc.). Es lo que
    # va al DEBE del asiento de cobranza. El contador dijo que es fondo fijo,
    # así que por lo general se completa solo con la cuenta fija de
    # Configuración y no se pregunta en el formulario. Cada recibo guarda la
    # que usó, para que cambiar la fija después no reescriba los viejos.
    cuenta_cobro_id: Mapped[int | None] = mapped_column(
        ForeignKey("plan_cuentas.id_cuenta", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True,
    )
    estado: Mapped[str] = mapped_column(
        Enum(*ESTADOS_RECIBO, name="estado_recibo"), nullable=False, default="emitido"
    )

    creado: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    actualizado: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    cliente = relationship("Cliente")
    cuenta_cobro = relationship("PlanCuenta")
    aplicaciones: Mapped[list["Aplicacion"]] = relationship(  # noqa: F821
        back_populates="recibo", cascade="all, delete-orphan"
    )
    pagos: Mapped[list["ReciboPago"]] = relationship(  # noqa: F821
        back_populates="recibo", cascade="all, delete-orphan"
    )
    # El asiento contable que se generó a partir de este recibo, si hay. NO son
    # columnas: salen de `asiento_origen` (origen = 'RECIBO'), se rellenan en
    # memoria para no tener que hacer la consulta en cada pantalla.
    #
    # OJO: sin anotación de tipo. Con `Mapped[...]` SQLAlchemy crea una
    # columna nueva y el INSERT manda `id_asiento` a MySQL, que no la tiene
    # (error 1054). Un atributo pelado no se mapea.
    id_asiento = None
    estado_asiento = None
    numero_comprobante_asiento = None

    @property
    def cuenta_cobro_codigo(self) -> str | None:
        return self.cuenta_cobro.codigo if self.cuenta_cobro else None

    @property
    def cuenta_cobro_nombre(self) -> str | None:
        return self.cuenta_cobro.nombre if self.cuenta_cobro else None

    @property
    def cliente_nombre(self) -> str:
        return self.cliente.nombre_completo if self.cliente else ""


class ReciboPago(Base):
    """Con qué se pagó UN recibo. Un recibo puede tener VARIOS pagos.

    Es lo que resuelve "un cliente paga 1.000.000 con dos bancos": en vez de
    elegir una sola cuenta y perder el resto, cada medio queda en su fila con su
    importe y su cuenta, y el asiento sale de acá (un Debe por pago, un solo
    Haber a Documentos a cobrar por el total).

    `cuenta_id` puede quedar en NULL: eso significa "el contador todavía no
    eligió el banco". Al asentar, el backend avisa en vez de inventar la cuenta.

    Los recibos cargados antes de esta tabla NO tienen pagos y siguen usando
    `recibo.cuenta_cobro_id`: el camino viejo no se rompe.
    """

    __tablename__ = "recibo_pagos"

    id_pago: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recibo_id: Mapped[int] = mapped_column(
        ForeignKey("recibos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    forma_pago: Mapped[str] = mapped_column(
        Enum(*FORMAS_PAGO, name="forma_pago_pago"), nullable=False
    )
    importe: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    # La cuenta que va en el DEBE del asiento de cobranza.
    cuenta_id: Mapped[int | None] = mapped_column(
        ForeignKey("plan_cuentas.id_cuenta", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True,
    )
    detalle: Mapped[str | None] = mapped_column(String(200), nullable=True)
    creado: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    recibo = relationship("Recibo", back_populates="pagos")
    cuenta = relationship("PlanCuenta")

    @property
    def cuenta_codigo(self) -> str | None:
        return self.cuenta.codigo if self.cuenta else None

    @property
    def cuenta_nombre(self) -> str | None:
        return self.cuenta.nombre if self.cuenta else None


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
