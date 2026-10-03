from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Variante(Base):
    """Variante de selección (idea SAP): filtros guardados por pantalla."""

    __tablename__ = "variantes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id"), nullable=False, index=True
    )
    pantalla: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(60), nullable=False)
    filtros: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    compartida: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    creado: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    actualizado: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "usuario_id",
            "pantalla",
            "nombre",
            name="uq_variante_usuario",
        ),
    )
