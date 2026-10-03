"""Cada tipo de gasto pertenece a un centro de costos.

Agrega tipos_gasto.centro_costo_id y lo rellena según la lista del cliente:
todo a Administración salvo Publicidad y Combustible (Comercialización).
"""

from sqlalchemy import text

from app.database import engine

COMERCIALIZACION = {"Publicidad", "Combustible"}


def columnas(conn):
    return {r[0] for r in conn.execute(text("SHOW COLUMNS FROM tipos_gasto"))}


with engine.begin() as conn:
    if "centro_costo_id" not in columnas(conn):
        conn.execute(text("ALTER TABLE tipos_gasto ADD COLUMN centro_costo_id INT NULL"))
        conn.execute(text("CREATE INDEX ix_tipos_gasto_centro ON tipos_gasto (centro_costo_id)"))
        conn.execute(
            text(
                "ALTER TABLE tipos_gasto ADD CONSTRAINT fk_tipos_gasto_centro "
                "FOREIGN KEY (centro_costo_id) REFERENCES centros_costos (id)"
            )
        )
        print("+ columna centro_costo_id + FK")
    else:
        print("= columna centro_costo_id ya existe")

    centros = {
        r[0]: r[1]
        for r in conn.execute(text("SELECT nombre, id FROM centros_costos"))
    }
    if "Administración" not in centros or "Comercialización" not in centros:
        raise SystemExit("Faltan centros: correr seed.py primero")

    sin_centro = conn.execute(
        text("SELECT id, nombre FROM tipos_gasto WHERE centro_costo_id IS NULL")
    ).all()
    for tid, nombre in sin_centro:
        centro = "Comercialización" if nombre in COMERCIALIZACION else "Administración"
        conn.execute(
            text("UPDATE tipos_gasto SET centro_costo_id = :c WHERE id = :i"),
            {"c": centros[centro], "i": tid},
        )
        print(f"  {nombre} -> {centro}")

    conn.execute(text("ALTER TABLE tipos_gasto MODIFY centro_costo_id INT NOT NULL"))
    print("  centro_costo_id a NOT NULL")

print("Listo.")
