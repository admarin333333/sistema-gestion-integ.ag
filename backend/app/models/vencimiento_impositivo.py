from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, SmallInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# Catálogo de impuestos (se carga mes a mes porque ARCA no siempre vence el mismo día).
IMPUESTOS = (
    ("ddjj_iva", "DDJJ IVA"),
    ("sicore_cta", "SICORE - Pago a cuenta"),
    ("ddjj_sicore", "DDJJ SICORE"),
    ("ddjj_ganancias", "DDJJ Impuesto a las Ganancias"),
    ("monotributo", "Monotributo"),
    ("convenio_multilateral", "Convenio multilateral"),
    ("anticipo_fondo_coop", "Anticipo Fondo Cooperativo"),
    ("ddjj_fondo_coop", "DDJJ Fondo Cooperativo"),
)

ETIQUETAS_IMPUESTO = dict(IMPUESTOS)


class VencimientoImpositivo(Base):
    """Fecha de vencimiento de un impuesto para un mes/año y un dígito de CUIT.

    El dígito es el último del CUIT del cliente (0 a 9): todos los clientes que
    terminan igual vencen el mismo día. Se carga mes a mes porque los vencimientos
    de ARCA cambian.
    """

    __tablename__ = "vencimientos_impositivos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Período (el mes que se está configuring).
    anio: Mapped[int] = mapped_column(SmallInteger, nullable=False, index=True)
    mes: Mapped[int] = mapped_column(SmallInteger, nullable=False, index=True)

    # A qué grupo de clientes aplica: el último dígito del CUIT (0..9).
    ultimo_digito: Mapped[int] = mapped_column(SmallInteger, nullable=False, index=True)

    # Qué impuesto y cuándo vence.
    impuesto: Mapped[str] = mapped_column(String(40), nullable=False)
    fecha_vencimiento: Mapped[date] = mapped_column(Date, nullable=False)

    creado: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    actualizado: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "anio", "mes", "ultimo_digito", "impuesto", name="uq_venc_periodo_digito_impuesto"
        ),
    )