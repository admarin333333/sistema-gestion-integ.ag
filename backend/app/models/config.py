"""
LAS CUATRO TABLAS DE CONFIGURACIÓN, ahora con modelo de SQLAlchemy.

POR QUÉ EXISTE ESTE ARCHIVO

Estas cuatro tablas ya estaban en la base desde antes de que hubiera Alembic, y el
sistema las usa todos los días. Hasta ahora se consultaban **con SQL a mano** en
los routers (`text("SELECT codigo, nombre FROM config_comprobantes")`), sin
modelo.

Eso dejaba a Alembic en una situación peligrosa: una tabla que está en la base y
no en `Base.metadata` es, para el autogen, una tabla sobrante. Con
`--autogenerate` proponía **borrarlas**. Con 11 tipos de comprobante y 6 formas de
pago adentro, aplicar esa migración dejaba el sistema sin poder facturar.

Había dos salidas:

1. Decirle a Alembic que las ignore con `include_object` en `migraciones/env.py`.
   Simple, pero es una photo: mientras estén en esa lista, nadie las ve, y el día
   que alguien agregue una columna no se va a detectar.

2. **Modelarlas.** Es lo que se hizo acá.

El punto 2 además tiene un beneficio que el 1 no: con el modelo, **Alembic crea
estas tablas en una base nueva**. Sin ellas, una base armada desde cero no
puede facturar, porque no tendría los tipos de comprobante ni las cuentas por
forma de pago.

QUÉ NO SE TOCÓ

**El SQL a mano sigue igual.** Los routers que hacen `text("SELECT ... FROM
config_comprobantes")` no se cambiaron ni una línea. Modelar una tabla no obliga
a dejar de usarla con SQL: la hace *visible* para Alembic, que es otra cosa.

Cada modelo copia **exactamente** los tipos, la longitud y los nulos de la base.
Si un modelo dice `String(100)` y la base tiene `VARCHAR(200)`, Alembic propondría
modificar la columna: no hay que "aproximar", hay que copiar.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ConfigSistema(Base):
    """
    Configuración suelta del sistema, en pares clave/valor.

    Hoy tiene una sola fila (`cuenta_cobro_fija`, la cuenta donde entra la plata
    de los recibos), pero la tabla es genérica a propósito: lo que mañana sea
    "de dónde saco el número de comprobante" entra acá como otra clave.

    `clave` es la clave primaria y no un `id`: no hay dos filas con la misma
    clave, y eso es lo que hace el sistema.
    """

    __tablename__ = "config_sistema"

    clave: Mapped[str] = mapped_column(String(40), primary_key=True)
    valor: Mapped[str] = mapped_column(String(200), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(200), nullable=True)
    actualizado: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ConfigComprobante(Base):
    """
    Los tipos de comprobante y sus códigos (`FV`, `RC`, `NC`, `ND`, `AB`...).

    Es de donde salen las letras del número del comprobante y de dónde el sistema
    sabe si un asiento es automático o manual. Sin esta tabla no se puede
    facturar.

    `origen` dice de qué motor viene cada uno (`MANUAL`, `FACTURA`, `RECIBO`...):
    es lo que usa el generador de asientos para decidir qué hacer.
    """

    __tablename__ = "config_comprobantes"

    id_comprobante_tipo: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    codigo: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    origen: Mapped[str | None] = mapped_column(String(20), nullable=True)
    activa: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )


class ConfigCuentaFormaPago(Base):
    """
    Qué cuenta contable va por forma de pago, y si esa forma pide banco.

    `requiere_banco` es lo que hace que el recibo pida elegir una cuenta
    bancaria del cliente: efectivo y chequeo no la piden, transferencia sí.

    La clave primaria es `forma_pago` (el texto), no un `id`: una forma de pago
    es una sola fila y se la busca por nombre.

    **OJO con `cuenta_id`: NO lleva `index=True`.** La base ya tiene un índice
    sobre esa columna, que MySQL creó con el nombre de la clave foránea
    (`fk_config_fp_cuenta`). Si el modelo dice `index=True`, Alembic ve que falta
    un índice llamado `ix_config_cuentas_forma_pago_cuenta_id` y propone
    agregarlo: un segundo índice sobre la misma columna, inútil y más lento.
    Lo mismo con las cuatro cuentas de `ConfigAsiento`.
    """

    __tablename__ = "config_cuentas_forma_pago"

    forma_pago: Mapped[str] = mapped_column(String(20), primary_key=True)
    # Con el nombre de la clave foránea que tiene en la base: si el modelo la
    # declara sin nombre, Alembic propone borrarla y recrearla.
    cuenta_id: Mapped[int | None] = mapped_column(
        ForeignKey("plan_cuentas.id_cuenta", name="fk_config_fp_cuenta", onupdate="CASCADE", ondelete="RESTRICT"), nullable=True
    )
    requiere_banco: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    descripcion: Mapped[str | None] = mapped_column(String(200), nullable=True)


class ConfigAsiento(Base):
    """
    Qué cuenta va en cada renglón del asiento, según el tipo de operación.

    Cada fila es una combinación (clave, nombre) con cuatro cuentas: la que
    lleva el Debe del documento, la del Haber de ingresos, la del IVA y la de
    cobranza. El generador de asientos lee esta tabla para armar el comprobante.

    Las cuatro cuentas apuntan a `plan_cuentas` y pueden ser `NULL`: una
    combinación que no use cobranza, por ejemplo, deja esa en blanco.
    """

    __tablename__ = "config_asientos"

    id_config: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clave: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    cuenta_debe: Mapped[int | None] = mapped_column(
        ForeignKey("plan_cuentas.id_cuenta", name="fk_cfg_debe", onupdate="CASCADE", ondelete="RESTRICT"), nullable=True
    )
    cuenta_haber_ingresos: Mapped[int | None] = mapped_column(
        ForeignKey("plan_cuentas.id_cuenta", name="fk_cfg_ingresos", onupdate="CASCADE", ondelete="RESTRICT"), nullable=True
    )
    cuenta_haber_iva: Mapped[int | None] = mapped_column(
        ForeignKey("plan_cuentas.id_cuenta", name="fk_cfg_iva", onupdate="CASCADE", ondelete="RESTRICT"), nullable=True
    )
    cuenta_haber_cobranza: Mapped[int | None] = mapped_column(
        ForeignKey("plan_cuentas.id_cuenta", name="fk_cfg_cobranza", onupdate="CASCADE", ondelete="RESTRICT"), nullable=True
    )
    activa: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )