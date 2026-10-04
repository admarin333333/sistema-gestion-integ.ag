"""
CUENTAS BANCARIAS DE LOS CLIENTES: el catálogo de bancos y las cuentas.

Un cliente puede tener todas las cuentas que quiera: son varias filas de
`ctas_barias_clientes` apuntando al mismo `id_cliente`. Por eso la tabla de
cuentas NO tiene una FK a `clientes` con unicidad: justamente tiene que poder
repetir.

Por qué dos tablas: el CBU ya trae el banco adentro (los primeros 8 dígitos son
el código del banco ante el BCRA). Con el código como clave primaria de `bancos`,
el banco nunca se duplica con distinta forma de escribirlo, y se puede verificar
que un CBU pertenezca al banco que dice pertenecer.

**CBU y CVU van en columnas separadas y no se pueden usar los dos a la vez**:
el CBU es una cuenta bancaria (tiene sucursal y número de cuenta) y el CVU es la
dirección de una billetera. Si se dejaran los dos, el contador no sabría cuál
copiar. La validación de eso está en el service, no en la base: la base no sabe
qué es un CBU.

**No se borran, se dan de baja.** Una cuenta puede estar usada en un recibo que
ya se emitió; borrarla dejaría ese recibo apuntando a una cuenta inexistente. Por
eso está `activo`.
"""

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

MONEDAS = ("ARS", "USD")


class Banco(Base):
    """
    El catálogo de bancos, por su código de 8 dígitos del BCRA.

    La clave primaria es el código y no un `id` autoincremental porque el código
    es lo que viene dentro del CBU: si fuera un `id`, habría que guardar el
    código aparte y nada impediría dos bancos con el mismo código.

    Empieza VACÍA a propósito: los códigos de los ~90 bancos no se inventan. Se
    cargan a medida que aparecen, y el primero se conoce solo cuando alguien
    pega un CBU y aparecen sus 8 primeros dígitos.
    """

    __tablename__ = "bancos"

    codigo: Mapped[str] = mapped_column(String(8), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80), nullable=False)
    # Permite dejar de ofrecer un banco sin borrar el histórico de las cuentas que
    # lo usan: la FK es RESTRICT, así que borrar el banco no se puede.
    activo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )

    cuentas: Mapped[list["CtaBariaCliente"]] = relationship(
        back_populates="banco", lazy="select"
    )


class CtaBariaCliente(Base):
    """
    Una cuenta bancaria (o una billetera) de UN cliente.

    `sucursal` y `numero_cuenta` van como texto y no como número: en un CBU los
    ceros adelante son válidos ("0001"), y como número desaparecen. Lo mismo con
    `alias_cbu`: el alias admite letras, guiones y puntos.
    """

    __tablename__ = "ctas_barias_clientes"
    __table_args__ = (
        Index("ix_cta_cliente_activo", "id_cliente", "activo"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_cliente: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # El código del banco, tal cual viene en el CBU. FK RESTRICT: no se puede borrar
    # un banco que tiene cuentas.
    codigo_banco: Mapped[str] = mapped_column(
        ForeignKey("bancos.codigo", ondelete="RESTRICT"), nullable=False
    )
    sucursal: Mapped[str | None] = mapped_column(String(10), nullable=True)
    numero_cuenta: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # 22 dígitos. CBU y CVU son mutuamente excluyentes (lo valida el service).
    cbu: Mapped[str | None] = mapped_column(String(22), nullable=True, index=True)
    cvu: Mapped[str | None] = mapped_column(String(22), nullable=True)
    alias_cbu: Mapped[str | None] = mapped_column(String(40), nullable=True)
    cuit_titular: Mapped[str | None] = mapped_column(String(13), nullable=True)
    # El CBU NO dice en qué moneda está la cuenta: un banco puede tener cuentas en
    # pesos y en dólares con el mismo código. Por eso la moneda va acá y no en el
    # banco.
    moneda: Mapped[str] = mapped_column(
        String(3), nullable=False, default="ARS", server_default="ARS"
    )
    activo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    creado: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    banco: Mapped[Banco] = relationship(back_populates="cuentas", lazy="joined")