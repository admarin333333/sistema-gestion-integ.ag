from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Servicio(Base):
    """Catálogo fijo de los servicios que ofrece el estudio."""

    __tablename__ = "servicios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    orden: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    clientes: Mapped[list["Cliente"]] = relationship(  # noqa: F821
        secondary="cliente_servicio",
        back_populates="servicios",
        lazy="selectin",
    )


class ClienteServicio(Base):
    """Relación N <-> N: un cliente puede tener varios servicios a la vez."""

    __tablename__ = "cliente_servicio"

    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"),
        primary_key=True,
    )
    servicio_id: Mapped[int] = mapped_column(
        ForeignKey("servicios.id", ondelete="RESTRICT"),
        primary_key=True,
    )
