from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Ejercicio(Base):
    """El **ejercicio contable del estudio**, o sea de la empresa que usa el
    software.

    OJO, que esto se confunde con el ejercicio de cada cliente:

    - **Acá** es el del estudio. Marca desde qué fecha se puede asentar y
      cuándo se reinicia la numeración de los documentos internos.
    - El **de cada cliente** está en otra tabla, `bal_rt54_ejercicios`, y cada
      uno tiene su propia fecha de cierre (unos cierran en junio, otros en
      diciembre). Ese NO se toca desde acá.

    El motivo de que existan los dos es que no tienen por qué coincidir: el
    estudio puede cerrar el 31/08 y el cliente auditado el 30/06.
    """

    __tablename__ = "ejercicios"

    id_ejercicio: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    # "2026/2027", a criterio del contador. Lo elige él, no se arma solo.
    nombre: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    fecha_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_fin: Mapped[date] = mapped_column(Date, nullable=False)

    # Un ejercicio cerrado no recibe más asientos. Se usa para el cierre de
    # ejercicio: nadie puede meter nada abajo de una fecha ya cerrada.
    cerrado: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    # OJO el doble default.
    #
    # `default=datetime.utcnow` lo pone Python: sirve cuando el INSERT lo hace
    # el ORM.
    #
    # `server_default` lo pone MySQL: sirve cuando el INSERT lo hace SQL crudo,
    # que es lo que hacen los scripts de arranque (`migrar_ejercicios.py`). Sin
    # él, la columna queda NOT NULL sin default y cualquier INSERT que no la
    # nombre explícitamente falla con "Field 'creado' doesn't have a default
    # value".
    #
    # Los dos hacen falta. El `server_default` además es lo que ya tiene la base
    # del estudio, así que una base nueva queda igual que esa.
    creado: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    actualizado: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover - solo para depurar
        return f"<Ejercicio {self.nombre}>"