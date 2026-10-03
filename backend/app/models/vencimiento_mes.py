from datetime import datetime

from sqlalchemy import DateTime, Integer, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class VencimientoMes(Base):
    """Un registro por cada mes/año de vencimientos que se guardó.

    Tres cosas:
    - **cuándo** se guardó por última vez (lo muestra el árbol de Configuración);
    - **un respaldo** del último guardado, por si después hay que recuperar
      algo que se borró sin querer;
    - saber qué meses existen, aunque después los vacíes.
    """

    __tablename__ = "vencimientos_meses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    anio: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    mes: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    # Cuántos vencimientos tiene el mes ahora mismo.
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    ultimo_cambio: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    usuario: Mapped[str | None] = mapped_column(String(60), nullable=True)

    # Copia del último guardado (JSON), para poder restaurarlo.
    respaldo: Mapped[str | None] = mapped_column(Text, nullable=True)