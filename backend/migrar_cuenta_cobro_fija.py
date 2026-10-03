"""La cuenta de cobro fija: en qué cuenta entra la plata de los recibos.

El contador dijo que es **fondo fijo**: la misma cuenta siempre (por ejemplo, el
Banco Nación). Entonces se configura UNA vez acá y el recibo no lo pregunta.

Se guarda en `config_sistema` (clave/valor) y no como columna del recibo, porque:

- Es un valor del estudio, no del recibo. Si mañana se cambia (de Banco a
  Caja), no hay que tocar los recibos viejos: cada uno guarda la cuenta que
  usó en su momento.
- El recibo SÍ guarda su `cuenta_cobro_id`, que ya viene en la tabla. Al crear
  un recibo sin cuenta, se le pega la de acá.

Uso:  python -X utf8 migrar_cuenta_cobro_fija.py --ver
      python -X utf8 migrar_cuenta_cobro_fija.py
"""

import sys

from sqlalchemy import text

from app.database import engine

SQL_TABLA = """
CREATE TABLE IF NOT EXISTS config_sistema (
    clave       VARCHAR(40) NOT NULL PRIMARY KEY,
    valor       VARCHAR(200) NOT NULL,
    descripcion VARCHAR(200) NULL,
    actualizado DATETIME NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

# La clave de configuración y qué dice.
CLAVE = "cuenta_cobro_fija"

# Con qué cuenta se siembra: el Banco Nación del plan RT54. Si el plan de esta
# base no lo tiene, se deja sin valor y el contador la elige en la pantalla.
CUENTA_POR_DEFECTO = "1.1.01.03"

DESCRIPCION = (
    "Cuenta donde entra la plata de los recibos. Se usa sola si el recibo no "
    "indica otra."
)


# La FK que faltaba: `cuenta_cobro_id` quedó como un INT suelto cuando se
# agregó la columna, y sin ella el backend no puede mostrar el código y el
# nombre de la cuenta en el recibo (SQLAlchemy no arma la relación).
SQL_FK_RECIBO = (
    "ALTER TABLE recibos "
    "ADD CONSTRAINT fk_recibo_cuenta_cobro "
    "FOREIGN KEY (cuenta_cobro_id) REFERENCES plan_cuentas (id_cuenta) "
    "ON DELETE RESTRICT ON UPDATE CASCADE"
)


def _tiene_constraint(conn, nombre):
    return bool(
        conn.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.table_constraints "
                "WHERE constraint_schema = DATABASE() AND constraint_name = :n"
            ),
            {"n": nombre},
        ).scalar()
    )


def _tiene_tabla(conn, nombre):
    return bool(
        conn.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name = :n"
            ),
            {"n": nombre},
        ).scalar()
    )


def main():
    solo_ver = "--ver" in sys.argv

    with engine.connect() as conn:
        print("=== ANTES ===")
        print(f"  tabla config_sistema: "
              f"{'ya existe' if _tiene_tabla(conn, 'config_sistema') else 'no existe'}")
        if _tiene_tabla(conn, "config_sistema"):
            for r in conn.execute(text("SELECT clave, valor FROM config_sistema")):
                print(f"  {r[0]} = {r[1]}")

    if solo_ver:
        print("\n(--ver: no se escribió nada)")
        return

    with engine.begin() as conn:
        conn.execute(text(SQL_TABLA))
        print("\n  tabla config_sistema creada")

        if not _tiene_constraint(conn, "fk_recibo_cuenta_cobro"):
            conn.execute(text(SQL_FK_RECIBO))
            print("  FK recibos.cuenta_cobro_id -> plan_cuentas")

        cuenta = conn.execute(
            text("SELECT id_cuenta FROM plan_cuentas WHERE codigo = :c"),
            {"c": CUENTA_POR_DEFECTO},
        ).scalar()

        if cuenta is None:
            print(f"  No encontré la cuenta {CUENTA_POR_DEFECTO} en el plan: "
                  "queda sin valor fijo.")
            print("  Cargá el plan de cuentas primero (migrar_plan_cuentas.py).")
            return

        conn.execute(
            text(
                "INSERT INTO config_sistema (clave, valor, descripcion) "
                "VALUES (:k, :v, :d) "
                "ON DUPLICATE KEY UPDATE valor = VALUES(valor), "
                "descripcion = VALUES(descripcion)"
            ),
            {"k": CLAVE, "v": str(cuenta), "d": DESCRIPCION},
        )
        print(f"  cuenta de cobro fija = {CUENTA_POR_DEFECTO} (id {cuenta})")

    with engine.connect() as conn:
        print("\n=== DESPUÉS ===")
        for r in conn.execute(text("SELECT clave, valor, descripcion FROM config_sistema")):
            print(f"  {r[0]} = {r[1]}")
            print(f"      {r[2]}")


if __name__ == "__main__":
    main()