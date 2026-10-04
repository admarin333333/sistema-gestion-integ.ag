"""Las compras se asientan: la cuenta de gasto sale del PLAN DE CUENTAS.

Qué cambia:

  1. `compras.cuenta_gasto_id` — la cuenta 6.x que se debita (6.1.03 luz-agua,
     6.2.01 publicidad...). El centro de costos sale de esa cuenta, así que el
     informe por centro nunca puede contradecir al plan.

  2. `centro_costo_id` y `tipo_gasto_id` pasan a NULL: el centro y el tipo de
     gasto eran una lista paralela que ya se contradecía con el plan
     (Intereses estaba en Administración cuando en el plan es Financiero).
     NO SE BORRA NADA: la columna queda con lo que hubiera.

  3. `asiento_origen.id_compra` — hasta ahora solo había `id_factura` e
     `id_recibo`, así que no se podía saber de qué compra salía un asiento.

  4. El comprobante interno `FP` (factura de proveedor) para las compras.

No se borra ninguna fila. El script se puede correr N veces.
"""

from sqlalchemy import text

from app.database import engine


def columnas(conn, tabla):
    return {r[0] for r in conn.execute(text(f"SHOW COLUMNS FROM {tabla}"))}


def indices(conn, tabla):
    # `SHOW INDEX` devuelve: Tabla, Non_unique, Key_name, ...
    # El nombre del índice es la TERCERA columna (índice 2). Con `r[0]` se
    # leía el nombre de la TABLA, así que la lista era siempre {tabla} y la
    # comprobación "el índice ya existe" nunca daba True: el script intentaba
    # crear el índice en cada corrida y MySQL contestaba
    # "Duplicate key name 'uq_origen_compra'".
    return {r[2] for r in conn.execute(text(f"SHOW INDEX FROM {tabla}"))}


def constraints(conn, tabla):
    return {
        r[0]
        for r in conn.execute(
            text(
                "SELECT CONSTRAINT_NAME FROM information_schema.TABLE_CONSTRAINTS "
                "WHERE TABLE_NAME = :t"
            ),
            {"t": tabla},
        )
    }


with engine.begin() as conn:
    # --- 1 y 2: la cuenta de gasto de la compra -------------------------
    cols = columnas(conn, "compras")
    if "cuenta_gasto_id" not in cols:
        conn.execute(
            text("ALTER TABLE compras ADD COLUMN cuenta_gasto_id INT NULL")
        )
        conn.execute(
            text(
                "ALTER TABLE compras ADD CONSTRAINT fk_compra_cuenta_gasto "
                "FOREIGN KEY (cuenta_gasto_id) REFERENCES plan_cuentas (id_cuenta) "
                "ON DELETE RESTRICT ON UPDATE CASCADE"
            )
        )
        print("+ compras.cuenta_gasto_id + FK a plan_cuentas")
    else:
        print("= compras.cuenta_gasto_id ya existe")

    # El centro y el tipo dejan de ser obligatorios. Sin esto, el INSERT de una
    # compra nueva falla porque las columnas siguen siendo NOT NULL.
    for col in ("centro_costo_id", "tipo_gasto_id"):
        info = conn.execute(
            text(
                "SELECT IS_NULLABLE FROM information_schema.COLUMNS "
                "WHERE TABLE_NAME = 'compras' AND COLUMN_NAME = :c"
            ),
            {"c": col},
        ).scalar()
        if info == "NO":
            conn.execute(
                text(f"ALTER TABLE compras MODIFY COLUMN {col} INT NULL")
            )
            print(f"~ compras.{col} ahora acepta NULL (el dato viejo queda)")
        else:
            print(f"= compras.{col} ya acepta NULL")

    # --- 3: de qué compra sale el asiento -------------------------------
    cols = columnas(conn, "asiento_origen")
    if "id_compra" not in cols:
        conn.execute(text("ALTER TABLE asiento_origen ADD COLUMN id_compra INT NULL"))
        print("+ asiento_origen.id_compra")
    else:
        print("= asiento_origen.id_compra ya existe")

    if "uq_origen_compra" not in indices(conn, "asiento_origen"):
        conn.execute(
            text(
                "ALTER TABLE asiento_origen "
                "ADD UNIQUE KEY uq_origen_compra (origen, id_compra)"
            )
        )
        print("+ índice único uq_origen_compra (una compra, un asiento)")
    else:
        print("= uq_origen_compra ya existe")

    if "fk_origen_compra" not in constraints(conn, "asiento_origen"):
        conn.execute(
            text(
                "ALTER TABLE asiento_origen ADD CONSTRAINT fk_origen_compra "
                "FOREIGN KEY (id_compra) REFERENCES compras (id) "
                "ON DELETE RESTRICT ON UPDATE CASCADE"
            )
        )
        print("+ FK fk_origen_compra")
    else:
        print("= fk_origen_compra ya existe")

    # --- 4: el comprobante de las compras -------------------------------
    existe = conn.execute(
        text("SELECT 1 FROM config_comprobantes WHERE codigo = 'FP'")
    ).scalar()
    if not existe:
        conn.execute(
            text(
                "INSERT INTO config_comprobantes (codigo, nombre, origen, activa) "
                "VALUES ('FP', 'Factura de proveedor', 'COMPRA', 1)"
            )
        )
        print("+ comprobante FP (Factura de proveedor)")
    else:
        print("= comprobante FP ya existe")

print()
print("migración de compras a la cuenta del plan: lista")
