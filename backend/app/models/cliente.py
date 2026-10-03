from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Cliente(Base):
    """Módulo cliente: solo los datos específicos del módulo cliente."""

    __tablename__ = "clientes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    persona_id: Mapped[int] = mapped_column(
        ForeignKey("personas.id"), nullable=False, unique=True
    )
    nro_cuenta: Mapped[int] = mapped_column(Integer, nullable=False)

    persona: Mapped["Persona"] = relationship(  # noqa: F821
        back_populates="cliente",
        lazy="selectin",
    )

    # Los datos viven en `personas`; estas propiedades dejan que el resto del
    # código siga usando `cliente.nombre_completo`, `cliente.cuit`, etc.
    @property
    def nombre_completo(self) -> str:
        return self.persona.nombre_completo if self.persona else ""

    @property
    def domicilio_completo(self) -> str:
        return self.persona.domicilio if self.persona else ""

    def __getattr__(self, nombre: str):
        """Si el atributo no es de esta tabla, lo busca en la persona.

        Solo se ejecuta cuando el atributo normal no existe, así que los campos
        de `clientes` (id, nro_cuenta) y las relaciones siguen funcionando.
        """
        if nombre.startswith("_"):
            raise AttributeError(nombre)
        persona = self.__dict__.get("persona")
        if persona is not None:
            try:
                return getattr(persona, nombre)
            except AttributeError:
                pass
        raise AttributeError(nombre)
    servicios: Mapped[list["Servicio"]] = relationship(  # noqa: F821
        secondary="cliente_servicio",
        back_populates="clientes",
        lazy="selectin",
    )
    sugerencias: Mapped[list["Sugerencia"]] = relationship(  # noqa: F821
        back_populates="cliente",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="Sugerencia.fecha.desc()",
    )