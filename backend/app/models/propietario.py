from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Propietario(Base):
    """Datos del propietario del software (el estudio).

    Es una sola fila: se guarda una vez desde Configuración. Tiene hasta
    cuatro correos para mandar los avisos (si administra más de una persona).
    """

    __tablename__ = "propietario"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # --- quién es ---
    nombre: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    cuit: Mapped[str | None] = mapped_column(String(13), nullable=True)
    actividad: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # --- dónde está ---
    calle: Mapped[str | None] = mapped_column(String(30), nullable=True)
    numero_calle: Mapped[str | None] = mapped_column(String(10), nullable=True)
    localidad: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provincia: Mapped[str | None] = mapped_column(String(100), nullable=True)
    codigo_postal: Mapped[str | None] = mapped_column(String(4), nullable=True)
    telefono: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cod_area: Mapped[str | None] = mapped_column(String(5), nullable=True)

    # --- a quién se le avisa (hasta 4 correos) ---
    email_1: Mapped[str | None] = mapped_column(String(120), nullable=True)
    email_2: Mapped[str | None] = mapped_column(String(120), nullable=True)
    email_3: Mapped[str | None] = mapped_column(String(120), nullable=True)
    email_4: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # --- avisos que se mandan ---
    # `server_default` está porque la fila del propietario la crea
    # `migrar_propietario.py` con SQL crudo, y sin el default del servidor MySQL
    # rechaza el INSERT ("Field 'aviso_vencimientos' doesn't have a default
    # value"). El `default=True` sigue haciendo falta para los INSERT del ORM.
    aviso_vencimientos: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("1")
    )

    observaciones: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha_alta: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    creado: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    actualizado: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    @property
    def correos(self) -> list[str]:
        """Los correos cargados, en orden (para mandar los avisos)."""
        return [
            c
            for c in (self.email_1, self.email_2, self.email_3, self.email_4)
            if c
        ]

    @property
    def domicilio(self) -> str:
        partes = [p for p in (self.calle, self.numero_calle) if p]
        return " ".join(partes)