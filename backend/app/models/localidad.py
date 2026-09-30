from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Localidad(Base):
    """Localidad de la provincia con su código postal.

    Permite que al cargar un CP en el cliente se complete solo la localidad.
    """

    __tablename__ = "localidades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    codigo_postal: Mapped[str] = mapped_column(String(4), nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    provincia: Mapped[str] = mapped_column(String(60), nullable=False, default="Córdoba")
