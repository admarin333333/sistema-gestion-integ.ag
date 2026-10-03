from datetime import date, datetime

from sqlalchemy import (
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

# Los códigos internos del estudio. Antes eran FIJOS; desde el 02/10/2026 viven
# en la tabla `config_comprobantes` (que es la fuente de verdad). Esta tupla
# queda solo como respaldo para una base que todavía no tenga esa tabla.
#
# Ojo: esto NO es el `tipo_comprobante` de las facturas, que es el tipo FISCAL
# (A, B, C...). Acá son los internos que numeran los asientos.
CODIGOS_COMPROBANTE = ("AI", "OP", "RC", "CO", "TR", "AJ")

ESTADOS_COMPROBANTE = ("BORRADOR", "CONTABILIZADO", "ANULADO")

DESCRIPCION_COMPROBANTE = {
    "AI": "Asiento Inicial",
    "OP": "Orden de Pago",
    "RC": "Recibo de Cobranza",
    "CO": "Comprobante de Egreso",
    "TR": "Transferencia / Movimiento de Tesorería",
    "AJ": "Asiento de Ajuste",
}


class ComprobanteInterno(Base):
    """La cabecera numerada de un movimiento del estudio: OP-000125.

    El **código** y el **número** van separados, así se puede filtrar por tipo
    sin leer texto.

    El correlativo es por código y **por ejercicio**, no por año calendario:
    si el ejercicio va del 01/09/2026 al 31/08/2027, el número corre corrido
    (000001…000300) sin reiniciarse el 1 de enero, y recién al abrir el
    ejercicio siguiente vuelve a 000001.

    `anio` sigue existiendo y es el año de la fecha: sirve para filtrar por
    año, pero NO participa de la numeración.
    """

    __tablename__ = "comprobantes_internos"

    id_comprobante: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )

    codigo_comprobante: Mapped[str] = mapped_column(String(10), nullable=False)

    anio: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    numero: Mapped[int] = mapped_column(Integer, nullable=False)

    # El ejercicio al que pertenece. NULL solo en comprobantes viejos, que
    # se pueden completar a mano.
    id_ejercicio: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("ejercicios.id_ejercicio", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True,
    )

    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    concepto: Mapped[str] = mapped_column(String(200), nullable=False)
    estado: Mapped[str] = mapped_column(
        String(15), nullable=False, default="BORRADOR"
    )

    ejercicio = relationship("Ejercicio")

    asientos: Mapped[list["Asiento"]] = relationship(  # noqa: F821
        back_populates="comprobante", cascade="save-update, merge"
    )

    creado: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    actualizado: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "codigo_comprobante", "id_ejercicio", "numero", name="uq_comprobante"
        ),
    )

    @property
    def numero_completo(self) -> str:
        """Como se ve: OP-000125 (el número siempre con 6 dígitos)."""
        return f"{self.codigo_comprobante}-{self.numero:06d}"

    def __repr__(self) -> str:  # pragma: no cover - solo para depurar
        return f"<ComprobanteInterno {self.numero_completo}>"