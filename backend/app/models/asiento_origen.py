from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.asiento import Asiento

# De dónde salió el asiento: de una factura, de un recibo, de una compra, o
# cargado a mano.
ORIGENES = ("FACTURA", "RECIBO", "COMPRA", "MANUAL")


class AsientoOrigen(Base):
    """Liga un asiento con el registro que lo originó.

    Sirve para dos cosas, y las dos importantes:

    1. **No asentar dos veces lo mismo.** Los UNIQUE (origen, id_factura),
       (origen, id_recibo) y (origen, id_compra) son los que lo garantizan: si
       hacés doble clic en "guardar", el segundo intento choca contra la base y
       no duplica nada.
    2. **Anular junto.** Si anulás una factura, por acá se encuentra su asiento
       y se anula también. Si no, queda un movimiento fantasma en los libros.

    Una factura, un recibo o una compra pueden estar en un asiento SOLO de su
    tipo: un recibo genera un asiento de cobranza, nunca uno de venta.
    """

    __tablename__ = "asiento_origen"

    id_origen: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    id_asiento: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("asientos.id_asiento", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )
    origen: Mapped[str] = mapped_column(String(20), nullable=False)

    id_factura: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("facturas.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True,
    )
    id_recibo: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("recibos.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True,
    )

    id_compra: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("compras.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True,
    )

    asiento = relationship("Asiento")

    __table_args__ = (
        # Una factura no se asienta dos veces.
        UniqueConstraint("origen", "id_factura", name="uq_origen_factura"),
        # Un recibo tampoco.
        UniqueConstraint("origen", "id_recibo", name="uq_origen_recibo"),
        # Ni una compra.
        UniqueConstraint("origen", "id_compra", name="uq_origen_compra"),
    )

    def __repr__(self) -> str:  # pragma: no cover - solo para depurar
        return f"<AsientoOrigen {self.origen} asiento={self.id_asiento}>"