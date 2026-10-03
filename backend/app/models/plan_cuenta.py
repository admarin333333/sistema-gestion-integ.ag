from sqlalchemy import Boolean, ForeignKey, Integer, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PlanCuenta(Base):
    """El plan de cuentas del estudio, en una sola tabla jerárquica.

    No hay tablas separadas para rubros, subrubros y cuentas: todo vive acá y
    el nivel se deduce de cuántas partes tiene el `codigo`
    (1 = "1 ACTIVO", 2 = "1.1 ACTIVO CORRIENTE", 3 = "1.1.01 Caja y bancos"...)
    El vínculo con el padre es `cuenta_padre_id`, que puede ir vacío en las
    cuentas raíz.

    - **naturaleza**: BALANCE (activo, pasivo, patrimonio neto) o RESULTADO
      (ingresos, costos, gastos, resultados financieros). Define si la cuenta
      va al patrimonio o al resultado del ejercicio.
    - **deudora_acreadora**: de qué lado se acumula (Debe o Haber). Solo tiene
      sentido en las imputables: un agrupador puede mezclar las dos.
    - **imputable**: solo las hojas reciben movimientos contables. Un rubro o un
      agrupador es imputable = False y sirve para agrupar en los informes.
    - **tipo_auxiliar**: qué dato extra se le pide a cada movimiento
      (CLIENTE, PROVEEDOR, BANCO o NINGUNO). Va solo en las cuentas imputables.
    - **activa**: se apaga antes de borrarse, para no romper los asientos que
      ya la usan.
    """

    __tablename__ = "plan_cuentas"

    id_cuenta: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )

    # El código contable, como figura en el Excel: "1.1.01.01". Es único y no
    # se toca: los asientos lo referencian.
    codigo: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)

    nombre: Mapped[str] = mapped_column(String(150), nullable=False)

    # NULL en las cuentas raíz (los 7 grupos de nivel 1).
    cuenta_padre_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("plan_cuentas.id_cuenta", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True,
    )

    # Cuántas partes tiene el código: 1 = rubro, 4 = cuenta de cuarto nivel.
    nivel: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)

    # **BALANCE** = cuenta de patrimonio (activo, pasivo, patrimonio neto).
    # **RESULTADO** = cuenta del ejercicio (ingresos, costos, gastos,
    # resultados financieros). Sale del grupo de nivel 1 al que pertenece.
    naturaleza: Mapped[str] = mapped_column(
        String(10), nullable=False, default="BALANCE"
    )

    # De qué lado va el movimiento: **DEUDORA** (suma en el Debe) o
    # **ACREEDORA** (suma en el Haber). Solo tiene sentido en las cuentas
    # imputables: un agrupador puede mezclar las dos, así que va en NULL.
    deudora_acreadora: Mapped[str | None] = mapped_column(
        String(12), nullable=True
    )

    imputable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # "CLIENTE" | "PROVEEDOR" | "BANCO" | "NINGUNO"
    tipo_auxiliar: Mapped[str | None] = mapped_column(String(30), nullable=True)

    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Las subcuentas de esta, y el padre de cada una. En un vínculo a la propia
    # tabla hay que aclarar de qué lado está "el uno": `remote_side` va en el
    # lado muchos-a-uno (el padre). Si se pone del otro lado, las dos
    # relaciones quedan invertidas.
    hijas: Mapped[list["PlanCuenta"]] = relationship(
        "PlanCuenta",
        back_populates="padre",
        cascade="save-update, merge",
    )
    padre: Mapped["PlanCuenta | None"] = relationship(
        "PlanCuenta",
        back_populates="hijas",
        remote_side=lambda: [PlanCuenta.id_cuenta],
    )

    def __repr__(self) -> str:  # pragma: no cover - solo para depurar
        return f"<PlanCuenta {self.codigo} {self.nombre}>"