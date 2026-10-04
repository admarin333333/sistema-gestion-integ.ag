"""Pagos de un recibo: un recibo puede cobrarse con VARIAS formas de pago.

    python -X utf8 migrar_pagos_recibo.py [--ver]

## Por qué

Un cliente puede pagar 1.000.000 con dos bancos: 700.000 del Santander y
300.000 de un cheque. Con el modelo de hoy el recibo tiene UN solo
`cuenta_cobro_id`, así que hay que elegir uno y el otro se pierde.

Acá cada pago es una fila:

| Recibo 00000067 por 1.000.000 | | |
|---|---|---|
| transferencia | 700.000 | 1.1.01.05 Santander |
| cheque | 300.000 | 1.1.01.10 Valores a depositar |

El asiento sale de estas filas: un Debe por pago, y un solo Haber a Documentos a
cobrar por el total.

## Lo que cambia

- Se agrega la tabla `recibo_pagos`.
- **No se borra ni se toca** `recibos.cuenta_cobro_id`: los recibos ya
  cargados siguen teniendo su cuenta, y si no tienen pagos se sigue usando esa.
  Es el camino viejo, y funciona.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text  # noqa: E402

from app.database import engine  # noqa: E402

VER = "--ver" in sys.argv

SQL = """\
CREATE TABLE IF NOT EXISTS recibo_pagos (
    id_pago      INT AUTO_INCREMENT PRIMARY KEY,
    recibo_id    INT NOT NULL,
    forma_pago   VARCHAR(20) NOT NULL,
    importe      DECIMAL(14,2) NOT NULL,
    cuenta_id    INT NULL,        -- NULL = el contador todavía no la eligió
    detalle      VARCHAR(200) NULL,
    creado       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_pago_recibo
        FOREIGN KEY (recibo_id) REFERENCES recibos (id) ON DELETE CASCADE,
    CONSTRAINT fk_pago_cuenta
        FOREIGN KEY (cuenta_id) REFERENCES plan_cuentas (id_cuenta)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE INDEX idx_pago_recibo ON recibo_pagos (recibo_id);
"""

print("SQL que se va a aplicar:\n")
print(SQL)
print(
    "No toca `recibos.cuenta_cobro_id`: los recibos viejos siguen usando esa "
    "cuenta si no tienen pagos.\n"
)

if VER:
    print("--ver: no se aplicó nada.")
    raise SystemExit(0)

with engine.begin() as conn:
    # Se consulta information_schema antes: si ya existe (porque se corrió dos
    # veces), el CREATE reventaría con "Table already exists".
    ya = conn.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.TABLES "
            " WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'recibo_pagos'"
        )
    ).scalar()
    if ya:
        print("recibo_pagos: la tabla ya existía")
    else:
        conn.execute(
            text(
                "CREATE TABLE recibo_pagos ("
                "  id_pago    INT AUTO_INCREMENT PRIMARY KEY,"
                "  recibo_id  INT NOT NULL,"
                "  forma_pago VARCHAR(20) NOT NULL,"
                "  importe    DECIMAL(14,2) NOT NULL,"
                "  cuenta_id  INT NULL,"
                "  detalle    VARCHAR(200) NULL,"
                "  creado     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,"
                "  CONSTRAINT fk_pago_recibo"
                "    FOREIGN KEY (recibo_id) REFERENCES recibos (id) ON DELETE CASCADE,"
                "  CONSTRAINT fk_pago_cuenta"
                "    FOREIGN KEY (cuenta_id) REFERENCES plan_cuentas (id_cuenta)"
                "    ON DELETE RESTRICT ON UPDATE CASCADE"
                ") ENGINE=InnoDB"
            )
        )
        conn.execute(text("CREATE INDEX idx_pago_recibo ON recibo_pagos (recibo_id)"))
        print("recibo_pagos: tabla creada")

print("\n--- resumen ---")
with engine.connect() as conn:
    total = conn.execute(text("SELECT COUNT(*) FROM recibo_pagos")).scalar()
    print(f"  recibo_pagos: {total} filas")
    n_con_pagos = conn.execute(
        text("SELECT COUNT(DISTINCT recibo_id) FROM recibo_pagos")
    ).scalar()
    print(f"  recibos con pagos cargados: {n_con_pagos}")
    print(f"  recibos totales: {conn.execute(text('SELECT COUNT(*) FROM recibos')).scalar()}")

print("\nListo. Falta el modelo, el endpoint y la pantalla.")