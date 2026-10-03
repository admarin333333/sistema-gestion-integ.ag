from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Periodo(Base):
    """Un **mes de un ejercicio contable**, que se abre y se cierra.

    Ojo con "mes": es el mes **del ejercicio**, no el del calendario. Con el
    ejercicio del 01/09/2026 al 31/08/2027, el período 1 es septiembre 2026 y el
    12 es agosto 2027. Por eso el número va de 1 a 12 y no es el número de mes.

    Para qué sirve: es la trava que evita cambiar la historia sin darse cuenta.
    Con el período de septiembre cerrado, anular o modificar un recibo del 15/09
    rebota — que es distinto de cerrar el ejercicio entero, que hoy es lo único
    que existe y solo frena el alta de comprobantes.

    **Un período cerrado no bloquea leer.** Se sigue querying el Mayor, el
    informe de centros y los listados: cerrar es para no escribir, no para no
    mirar.

    Las fechas se guardan en la fila (y no se calculan al vuelo) para que la
    pregunta "¿esta fecha cae en un período cerrado?" sea un
    `WHERE fecha_inicio <= ? AND fecha_fin >= ?`, que usa índice.
    """

    __tablename__ = "periodos"

    id_periodo: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    id_ejercicio: Mapped[int] = mapped_column(
        ForeignKey("ejercicios.id_ejercicio", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )

    # 1 a 12: el mes del ejercicio, contando desde `ejercicios.fecha_inicio`.
    numero: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    # "Septiembre 2026". Se guarda para no tener que armarlo en cada pantalla.
    nombre: Mapped[str] = mapped_column(String(40), nullable=False)

    fecha_inicio: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    fecha_fin: Mapped[date] = mapped_column(Date, nullable=False)

    # Cerrado = no se le carga, ni se anula, ni se modifica nada con esa fecha.
    # Nace en False: el contador trabaja y va cerrando mes a mes.
    cerrado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Quién lo cerró y cuándo. Para cuando alguien pregunte "¿quién cerró
    # septiembre?" y no haya que ir a buscarlo.
    cerrado_por: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
    )
    cerrado_el: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    creado: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    actualizado: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    ejercicio = relationship("Ejercicio", lazy="selectin")

    def __repr__(self) -> str:  # pragma: no cover - solo para depurar
        return f"<Periodo {self.numero} {self.nombre} cerrado={self.cerrado}>"
