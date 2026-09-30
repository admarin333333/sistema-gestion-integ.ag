from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

ESTADOS = ("pendiente", "atendida")


class Sugerencia(Base):
    """Sugerencia que el estudio le aporta al cliente, con su fecha."""

    __tablename__ = "sugerencias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fecha: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    descripcion: Mapped[str] = mapped_column(String(500), nullable=False)
    estado: Mapped[str] = mapped_column(
        Enum(*ESTADOS, name="estado_sugerencia"),
        nullable=False,
        default="pendiente",
    )
    creado: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    cliente: Mapped["Cliente"] = relationship(  # noqa: F821
        back_populates="sugerencias"
    )
