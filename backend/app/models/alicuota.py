from sqlalchemy import Boolean, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AlicuotaIva(Base):
    """Catálogo de alícuotas de IVA (se dan de alta desde el panel)."""

    __tablename__ = "alicuotas_iva"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    porcentaje: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
