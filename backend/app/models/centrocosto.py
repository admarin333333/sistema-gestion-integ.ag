from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CentroCosto(Base):
    """Catálogo de centros de costos (se dan de alta desde Configuración)."""

    __tablename__ = "centros_costos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
