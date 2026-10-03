from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ConceptoVencimiento(Base):
    """Catálogo de conceptos de vencimiento (editable desde Configuración).

    Antes estaba fijo en el código y para agregar uno había que tocar Python.
    Ahora se dan de alta desde la pantalla: por ejemplo "Libro IVA Digital",
    que no es un impuesto pero también tiene fecha de vencimiento.
    """

    __tablename__ = "conceptos_vencimiento"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Identificador corto con que se guarda el vencimiento (ej.: "ddjj_f931").
    clave: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)

    # Lo que se ve en la grilla de Configuración y en la pantalla de consulta.
    nombre: Mapped[str] = mapped_column(String(80), nullable=False)

    orden: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)

    # Los que trae el sistema de fábrica: se les puede cambiar el nombre pero
    # no se pueden borrar (sí desactivar).
    sistema: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Si está inactivo no aparece en la grilla, pero los vencimientos ya
    # cargados se siguen viendo con su nombre.
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    creado: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    actualizado: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)