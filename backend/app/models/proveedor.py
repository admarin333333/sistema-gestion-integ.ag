from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Proveedor(Base):
    """Módulo proveedor: solo los datos específicos del módulo proveedor."""

    __tablename__ = "proveedores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    persona_id: Mapped[int] = mapped_column(
        ForeignKey("personas.id"), nullable=False, unique=True
    )
    nro_cuenta: Mapped[int] = mapped_column(Integer, nullable=False)

    persona: Mapped["Persona"] = relationship(  # noqa: F821
        back_populates="proveedor",
        lazy="selectin",
    )

    # Los datos viven en `personas`; estas propiedades dejan que el resto del
    # código siga usando `proveedor.nombre_completo`, `proveedor.cuit`, etc.
    @property
    def nombre_completo(self) -> str:
        return self.persona.nombre_completo if self.persona else ""

    @property
    def domicilio_completo(self) -> str:
        return self.persona.domicilio if self.persona else ""

    def __getattr__(self, nombre: str):
        """Si el atributo no es de esta tabla, lo busca en la persona."""
        if nombre.startswith("_"):
            raise AttributeError(nombre)
        persona = self.__dict__.get("persona")
        if persona is not None:
            try:
                return getattr(persona, nombre)
            except AttributeError:
                pass
        raise AttributeError(nombre)