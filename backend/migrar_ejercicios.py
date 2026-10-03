"""El ejercicio contable del ESTUDIO.

Agrega la tabla `ejercicios` y cuelga de ella los documentos internos, para que
la numeración reinicie al abrir un ejercicio y no el 1 de enero.

Que quede claro el alcance, porque es lo que más se confunde:

- `ejercicios` = el ejercicio del **estudio** (la empresa que usa el software).
- `bal_rt54_ejercicios` = el ejercicio de **cada cliente**. No se toca acá.

No tienen por qué coincidir: el estudio puede cerrar el 31/08 y el cliente
auditado el 30/06.

Lo que cambia en `comprobantes_internos`:
- + `id_ejercicio`.
- La clave única pasa de (código, año, número) a **(código, ejercicio,
  número)**. Ese es el cambio de fondo: FV-000001 arranca cuando se abre el
  ejercicio, no el 1 de enero.

La columna `anio` **se queda** (es el año de la fecha, sirve para filtrar) pero
deja de participar en la numeración.

Uso:  python -X utf8 migrar_ejercicios.py
      python -X utf8 migrar_ejercicios.py --ver    (solo muestra)
"""

import sys

from sqlalchemy import text

from app.database import engine

# ---------------------------------------------------------------- ejercicio
# Para esta empresa arranca el 01/09/2026 y cierra el 31/08/2027: son 12 meses.
EJERCICIO_INICIAL = {
    "nombre": "2026/2027",
    "fecha_inicio": "2026-09-01",
    "fecha_fin": "2027-08-31",
    "cerrado": False,
}

SQL_EJERCICIO = """
CREATE TABLE IF NOT EXISTS ejercicios (
    id_ejercicio INT AUTO_INCREMENT PRIMARY KEY,
    nombre       VARCHAR(40) NOT NULL UNIQUE,
    fecha_inicio DATE         NOT NULL,
    fecha_fin    DATE         NOT NULL,
    cerrado      BOOLEAN      NOT NULL DEFAULT FALSE,
    creado       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado  DATETIME     NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

SQL_COLUMNA = (
    "ALTER TABLE comprobantes_internos "
    "ADD COLUMN id_ejercicio INT NULL AFTER anio"
)

SQL_FK = (
    "ALTER TABLE comprobantes_internos "
    "ADD CONSTRAINT fk_comprobante_ejercicio "
    "FOREIGN KEY (id_ejercicio) REFERENCES ejercicios (id_ejercicio) "
    "ON DELETE RESTRICT ON UPDATE CASCADE"
)

SQL_CAMBIA_UNIQUE = (
    "ALTER TABLE comprobantes_internos DROP INDEX uq_comprobante",
    "ALTER TABLE comprobantes_internos "
    "ADD CONSTRAINT uq_comprobante UNIQUE (codigo_comprobante, id_ejercicio, numero)",
)

SQL_INDICE = (
    "CREATE INDEX ix_comprobantes_ejercicio ON comprobantes_internos (id_ejercicio)"
)


def _tiene_columna(conn, tabla: str, columna: str) -> bool:
    return bool(
        conn.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = :t "
                "AND column_name = :c"
            ),
            {"t": tabla, "c": columna},
        ).scalar()
    )


def _tiene_indice(conn, nombre: str) -> bool:
    return bool(
        conn.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.statistics "
                "WHERE table_schema = DATABASE() AND index_name = :n"
            ),
            {"n": nombre},
        ).scalar()
    )


def _tiene_tabla(conn, nombre: str) -> bool:
    return bool(
        conn.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name = :n"
            ),
            {"n": nombre},
        ).scalar()
    )


def columnas_del_unico(conn) -> list[str]:
    """Las columnas del índice uq_comprobante, en orden."""
    return [
        r[2]
        for r in conn.execute(
            text(
                "SELECT index_name, seq_in_index, column_name "
                "FROM information_schema.statistics "
                "WHERE table_schema = DATABASE() AND index_name = 'uq_comprobante' "
                "ORDER BY seq_in_index"
            )
        )
    ]


def main():
    solo_ver = "--ver" in sys.argv

    with engine.connect() as conn:
        print("=== ANTES ===")
        tablas = _tiene_tabla(conn, "ejercicios")
        print(f"  tabla ejercicios: {'ya existe' if tablas else 'no existe'}")
        col = _tiene_columna(conn, "comprobantes_internos", "id_ejercicio")
        print(f"  columna comprobantes_internos.id_ejercicio: "
              f"{'ya existe' if col else 'no existe'}")
        uniques = columnas_del_unico(conn)
        print(f"  clave única actual: ({', '.join(uniques)})")
        print(f"  comprobantes con datos: "
              f"{conn.execute(text('SELECT COUNT(*) FROM comprobantes_internos')).scalar()}")

    if solo_ver:
        print("\n(--ver: no se escribió nada)")
        return

    with engine.begin() as conn:
        # --- tabla ejercicios ---
        conn.execute(text(SQL_EJERCICIO))
        print("\n  tabla ejercicios creada")

        # --- el ejercicio del estudio, abierto y recibiendo asientos ---
        conn.execute(
            text(
                "INSERT INTO ejercicios "
                "(nombre, fecha_inicio, fecha_fin, cerrado) "
                "VALUES (:n, :i, :f, 0) "
                "ON DUPLICATE KEY UPDATE fecha_inicio = VALUES(fecha_inicio), "
                "fecha_fin = VALUES(fecha_fin)"
            ),
            {
                "n": EJERCICIO_INICIAL["nombre"],
                "i": EJERCICIO_INICIAL["fecha_inicio"],
                "f": EJERCICIO_INICIAL["fecha_fin"],
            },
        )
        print(f"  ejercicio {EJERCICIO_INICIAL['nombre']} "
              f"({EJERCICIO_INICIAL['fecha_inicio']} a "
              f"{EJERCICIO_INICIAL['fecha_fin']}) abierto y habilitado")

        # --- columna en comprobantes_internos ---
        if not _tiene_columna(conn, "comprobantes_internos", "id_ejercicio"):
            conn.execute(text(SQL_COLUMNA))
            print("  comprobantes_internos.id_ejercicio agregada")

        if not _tiene_indice(conn, "fk_comprobante_ejercicio"):
            conn.execute(text(SQL_FK))
            print("  clave foránea a ejercicios")

        # --- la clave única pasa a ser por ejercicio ---
        if "id_ejercicio" not in columnas_del_unico(conn):
            for sql in SQL_CAMBIA_UNIQUE:
                conn.execute(text(sql))
            print("  clave única cambiada a (código, ejercicio, número)")

        if not _tiene_indice(conn, "ix_comprobantes_ejercicio"):
            conn.execute(text(SQL_INDICE))
            print("  índice por ejercicio")

    # ------------------------------------------------------------ resumen
    with engine.connect() as conn:
        print("\n=== DESPUÉS ===")
        print("  ejercicios:")
        for r in conn.execute(
            text(
                "SELECT nombre, fecha_inicio, fecha_fin, cerrado "
                "FROM ejercicios ORDER BY fecha_inicio"
            )
        ):
            estado = "CERRADO" if r[3] else "abierto, habilitado"
            print(f"    {r[0]:<12} {r[1]} → {r[2]}   [{estado}]")
        print(f"  clave única de comprobantes_internos: "
              f"({', '.join(columnas_del_unico(conn))})")


if __name__ == "__main__":
    main()