from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BalanceEjercicio(Base):
    """Ejercicio de estados contables RT54 (entes con fines de lucro) de un cliente.

    La carátula se copia de la ficha del cliente al crear el ejercicio
    y después es editable a mano (cada cliente tiene sus fechas)."""

    __tablename__ = "bal_rt54_ejercicios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id"), nullable=False, index=True
    )
    nombre: Mapped[str] = mapped_column(String(60), nullable=False)  # "2025"
    fecha_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_fin: Mapped[date] = mapped_column(Date, nullable=False)

    # Ejercicio contable: el usuario elige el año de inicio y el de cierre, y el
    # día/mes de cierre viene del cliente (se repite todos los años). Con eso el
    # sistema arma el intervalo: (año+1) al día/mes de cierre, menos un día.
    anio_inicio: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    anio_fin: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    dia_mes_cierre: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    mes_cierre: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    # Carátula (datos de la entidad) — texto libre, editable por el contador.
    entidad: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    cuit: Mapped[str | None] = mapped_column(String(13), nullable=True)
    domicilio: Mapped[str | None] = mapped_column(String(160), nullable=True)
    actividad: Mapped[str | None] = mapped_column(String(120), nullable=True)
    actividad_secundaria: Mapped[str | None] = mapped_column(String(160), nullable=True)

    # Registro Público de Comercio (las fechas van "AAAA-MM-DD", texto).
    fecha_inscripcion_rpc: Mapped[str | None] = mapped_column(String(10), nullable=True)
    fecha_estatuto: Mapped[str | None] = mapped_column(String(10), nullable=True)
    fecha_modificacion_estatuto: Mapped[str | None] = mapped_column(String(10), nullable=True)
    fecha_vencimiento_entidad: Mapped[str | None] = mapped_column(String(10), nullable=True)
    matricula_rpc: Mapped[str | None] = mapped_column(String(40), nullable=True)
    identificacion_rpc: Mapped[str | None] = mapped_column(String(120), nullable=True)
    duracion_entidad: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unidad_medida: Mapped[str | None] = mapped_column(String(60), nullable=True)

    # Sociedad controlante y entes controlados.
    controlante_denominacion: Mapped[str | None] = mapped_column(String(120), nullable=True)
    controlante_domicilio: Mapped[str | None] = mapped_column(String(160), nullable=True)
    controlante_actividad: Mapped[str | None] = mapped_column(String(120), nullable=True)
    controlante_participacion: Mapped[str | None] = mapped_column(String(40), nullable=True)
    controlante_votos: Mapped[str | None] = mapped_column(String(40), nullable=True)
    entes_nota: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # Composición del capital: un renglón por tabla, como el modelo
    # (cap_circ = en circulación, cap_cart = en cartera).
    cap_circ_cantidad: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cap_circ_tipo: Mapped[str | None] = mapped_column(String(40), nullable=True)
    cap_circ_votos: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cap_circ_suscripto: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), nullable=True)
    cap_circ_integrado: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), nullable=True)
    cap_cart_cantidad: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cap_cart_tipo: Mapped[str | None] = mapped_column(String(40), nullable=True)
    cap_cart_votos: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cap_cart_suscripto: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), nullable=True)
    cap_cart_integrado: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), nullable=True)

    creado: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    actualizado: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("cliente_id", "nombre", name="uq_bal_rt54_cliente_ejercicio"),
    )


class BalanceValor(Base):
    """Importe cargado a mano en un rubro del balance (ejercicio / comparativo)."""

    __tablename__ = "bal_rt54_valores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ejercicio_id: Mapped[int] = mapped_column(
        ForeignKey("bal_rt54_ejercicios.id"), nullable=False, index=True
    )
    seccion: Mapped[str] = mapped_column(String(10), nullable=False)  # esp | er | eepn
    clave: Mapped[str] = mapped_column(String(60), nullable=False)
    valor_actual: Mapped[Decimal] = mapped_column(
        Numeric(16, 2), nullable=False, default=0
    )
    valor_anterior: Mapped[Decimal] = mapped_column(
        Numeric(16, 2), nullable=False, default=0
    )

    __table_args__ = (
        UniqueConstraint("ejercicio_id", "seccion", "clave", name="uq_bal_rt54_valor"),
    )


class BalanceNota(Base):
    """Texto de una nota a los estados contables (hoja "Notas" del modelo).

    `clave` es la nota del modelo ("1.1" … "2.26", "3.1" … "7"). Si no hay
    fila guardada, la celda de la plantilla queda como está."""

    __tablename__ = "bal_rt54_notas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ejercicio_id: Mapped[int] = mapped_column(
        ForeignKey("bal_rt54_ejercicios.id"), nullable=False, index=True
    )
    clave: Mapped[str] = mapped_column(String(10), nullable=False)
    texto: Mapped[str] = mapped_column(Text, nullable=False, default="")

    __table_args__ = (
        UniqueConstraint("ejercicio_id", "clave", name="uq_bal_rt54_nota"),
    )


class BalanceNotaCelda(Base):
    """Importe cargado a mano en un cuadro de composición de una nota.

    `clave` = "<nota>:<fila del Excel>:<columna>" (ej. "2.3:44:C").
    Los Subtotal/Total no se guardan: los calcula el backend."""

    __tablename__ = "bal_rt54_nota_celdas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ejercicio_id: Mapped[int] = mapped_column(
        ForeignKey("bal_rt54_ejercicios.id"), nullable=False, index=True
    )
    clave: Mapped[str] = mapped_column(String(30), nullable=False)
    valor: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("ejercicio_id", "clave", name="uq_bal_rt54_nota_celda"),
    )
