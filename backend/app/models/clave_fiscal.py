from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ClaveFiscalHistorial(Base):
    """Cada cambio de la clave fiscal de una persona (cuaderno de cambios).

    No hay una fila por persona: hay **una fila cada vez que la clave cambia**.
    Así se puede saber con qué clave se presentó cada cosa, aunque después el
    cliente la haya cambiado.
    """

    __tablename__ = "clave_fiscal_historial"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    persona_id: Mapped[int] = mapped_column(
        ForeignKey("personas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    clave_fiscal_anterior: Mapped[str | None] = mapped_column(String(11), nullable=True)
    clave_fiscal_nueva: Mapped[str | None] = mapped_column(String(11), nullable=True)
    fecha_cambio: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    usuario: Mapped[str | None] = mapped_column(String(60), nullable=True)