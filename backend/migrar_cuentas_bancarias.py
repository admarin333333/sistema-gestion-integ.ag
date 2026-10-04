"""
CUENTAS BANCARIAS DE LOS CLIENTES — dos tablas: el catálogo de bancos y las
cuentas de cada cliente.

    python -X utf8 migrar_cuentas_bancarias.py

Idempotente: se puede correr las veces que haga falta.

POR QUÉ DOS TABLAS Y NO UNA

El CBU ya trae el banco adentro: los primeros 8 dígitos son el código del banco
ante el BCRA. Si el banco se guardara como texto libre, quedaría "Galicia",
"GALICIA", "galicia" y el sistema no reconocería que son el mismo. Con la tabla
`bancos`, ese código de 8 dígitos es la clave primaria: es único, nunca se
duplica, y además sirve para **verificar que un CBU pertenezca al banco que dice
pertenecer**.

Un cliente puede tener todas las cuentas que quiera: `ctas_barias_clientes` tiene
muchas filas apuntando al mismo `id_cliente`.

CBU CONTRA CVU

No son lo mismo, y por eso van en columnas separadas:
  - **CBU** (22 dígitos): la cuenta de un banco. Tiene sucursal y número de
    cuenta.
  - **CVU** (22 dígitos): el de las billeteras (Mercado Pago y similares). No
    tiene cuenta bancaria: es una dirección para que depositen.

Una cuenta tiene **uno u otro**, nunca los dos: por eso se validan en la
aplicación, no en la base. Si se dejaran los dos, el sistema no sabría cuál
usar y el contador terminaría copiando el equivocado.

MONEDA

El CBU no dice en qué moneda está la cuenta. Un banco puede tener cuentas en
pesos y en dólares, y el código del banco es el mismo. Por eso `moneda` va en la
cuenta y no en el banco.

BAJA LÓGICA, NO BORRADO

Una cuenta puede estar usada en un recibo que ya se emitió. Si se borrara, ese
recibo quedaría apuntando a una cuenta que ya no existe. Por eso está `activo`:
dar de baja la esconde de las pantallas y de los selectores, pero el registro
sigue ahí.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import inspect, text

from app.database import engine

TABLA_BANCOS = "bancos"
TABLA_CUENTAS = "ctas_barias_clientes"

SQL_BANCOS = """
CREATE TABLE IF NOT EXISTS bancos (
    codigo    VARCHAR(8)  NOT NULL,
    nombre    VARCHAR(80) NOT NULL,
    activo    TINYINT(1)  NOT NULL DEFAULT 1,
    PRIMARY KEY (codigo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

# Los 4 dígitos de la sucursal y los del número de cuenta van como texto (VARCHAR),
# no como número: un CBU con ceros adelante ("0001") es válido, y como número
# esos ceros desaparecen.
SQL_CUENTAS = """
CREATE TABLE IF NOT EXISTS ctas_barias_clientes (
    id             INT NOT NULL AUTO_INCREMENT,
    id_cliente     INT NOT NULL,
    codigo_banco   VARCHAR(8) NOT NULL,
    sucursal       VARCHAR(10) NULL,
    numero_cuenta  VARCHAR(30) NULL,
    cbu            VARCHAR(22) NULL,
    cvu            VARCHAR(22) NULL,
    alias_cbu      VARCHAR(40) NULL,
    cuit_titular   VARCHAR(13) NULL,
    moneda         VARCHAR(3) NOT NULL DEFAULT 'ARS',
    activo         TINYINT(1) NOT NULL DEFAULT 1,
    creado         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY ix_cuenta_cliente (id_cliente),
    KEY ix_cuenta_cbu (cbu)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""


def existe(tabla: str) -> bool:
    return tabla in inspect(engine).get_table_names()


def paso_1_bancos():
    if existe(TABLA_BANCOS):
        print("  paso 1: la tabla 'bancos' ya estaba")
        return
    with engine.begin() as c:
        c.execute(text(SQL_BANCOS))
    print("  paso 1: creada la tabla 'bancos'")


def paso_2_cuentas():
    if existe(TABLA_CUENTAS):
        print("  paso 2: la tabla 'ctas_barias_clientes' ya estaba")
        return
    with engine.begin() as c:
        c.execute(text(SQL_CUENTAS))
        # La clave foránea va después de crear la tabla: MySQL no la acepta dentro
        # del CREATE si la tabla 'clientes' no existe todavía.
        c.execute(
            text(
                "ALTER TABLE ctas_barias_clientes "
                "ADD CONSTRAINT fk_cta_banc_cliente FOREIGN KEY (id_cliente) "
                "REFERENCES clientes (id) ON DELETE RESTRICT"
            )
        )
        c.execute(
            text(
                "ALTER TABLE ctas_barias_clientes "
                "ADD CONSTRAINT fk_cta_banc_banco FOREIGN KEY (codigo_banco) "
                "REFERENCES bancos (codigo) ON DELETE RESTRICT"
            )
        )
    print("  paso 2: creada la tabla 'ctas_barias_clientes' con sus dos FK")


def paso_3_revisar():
    with engine.begin() as c:
        print()
        print("  COMO QUEDO:")
        for t in (TABLA_BANCOS, TABLA_CUENTAS):
            cols = [
                r[0]
                for r in c.execute(
                    text(
                        "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                        "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=:t"
                    ),
                    {"t": t},
                ).all()
            ]
            print(f"    {t}: {', '.join(cols)}")

        print()
        print("  bancos cargados:", c.execute(text("SELECT COUNT(*) FROM bancos")).scalar())
        print(
            "  claves foraneas:",
            [
                r[0]
                for r in c.execute(
                    text(
                        "SELECT CONSTRAINT_NAME FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS "
                        "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=:t "
                        "AND CONSTRAINT_TYPE='FOREIGN KEY'"
                    ),
                    {"t": TABLA_CUENTAS},
                ).all()
            ],
        )


if __name__ == "__main__":
    print("Migración: cuentas bancarias de clientes")
    paso_1_bancos()
    paso_2_cuentas()
    paso_3_revisar()