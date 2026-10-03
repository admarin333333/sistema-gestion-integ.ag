from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TipoGasto(Base):
    """Catálogo de tipos de gasto (se dan de alta desde Configuración).

    Cada tipo pertenece a un centro de costos: al cargar un comprobante,
    elegido el centro solo se ofrecen sus tipos.
    """

    __tablename__ = "tipos_gasto"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    centro_costo_id: Mapped[int] = mapped_column(
        ForeignKey("centros_costos.id"), nullable=False, index=True
    )
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    centro: Mapped["CentroCosto"] = relationship(  # noqa: F821
        lazy="selectin",
    )
