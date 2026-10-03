from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class IndiceMoneda(Base):
    """Índice de moneda homogénea FACPCE (Resolución Técnica N° 6).

    Un registro por mes: `fecha` es siempre el día 1 del mes y `indice` el
    valor del IPC nacional empalme IPIM de ese mes.
    """

    __tablename__ = "config_indices_moneda"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fecha: Mapped[date] = mapped_column(Date, nullable=False, unique=True, index=True)
    indice: Mapped[Decimal] = mapped_column(Numeric(24, 12), nullable=False)
