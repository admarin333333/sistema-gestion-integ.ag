"""Respaldo de TODO lo que importa, antes de correr los tests.

**Por qué existe.** Los tests corren contra la base del estudio, la misma que
usa el contador. Varias suiteslimpian por SQL (porque la API, bien hecha, no
borra un asiento contabilizado). El 02/10/2026 eso costó caro: siete suites
hacían `DELETE FROM asientos` a secas y se llevaron todos los asientos reales.
No había respaldo de asientos, así que no se pudieron recuperar. El único `.sql`
que el proyecto generaba era el de clientes de prueba.

Este script lo arregla: escribe los `INSERT` de **todas** las tablas que
importan, en un solo archivo, listo para restaurar con MySQL.

Es el mismo estilo que `limpiar_clientes_prueba.py`, pero de todo en vez de
solo de los clientes. **No borra nada**: solo escribe.

Uso:  python -X utf8 respaldar_todo.py
      python -X utf8 respaldar_todo.py --destino D:\\copia
"""

import os
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

from sqlalchemy import text  # noqa: E402

from app.database import engine  # noqa: E402

# El respaldo toma **TODAS** las tablas de la base, sin lista a mano.
#
# La primera versión tenía una lista escrita a dedo y se olvidaba de 24 tablas:
# `bal_rt54_notas` (88 filas), `bal_rt54_valores` (238), `config_indices_moneda`
# (404)... todo eso se perdía y nadie se enteraba. La lista escrita a mano es
# justamente el error: el sistema crece y la lista no.
#
# Lo único que se deja afuera es la columna `password_hash` de `usuarios`: una
# contraseña con hash no va a un archivo de texto. Los usuarios sí se respaldan,
# solo sin el hash (al restaurar hay que volver a ponérselo, o usar
# `python crear_usuario.py`).
COLUMNAS_SECRETAS = {"password_hash"}

# Lo que se escribe en lugar del hash. Es un texto que no es el hash de nada:
# la cuenta queda inactivated, no se entra con una contraseña inventada. La
# columna es NOT NULL sin valor por defecto, así que la columna no se puede
# sacar del INSERT (MySQL lo rechaza) y hay que poner algo.
HASH_DE_RELLENO = "'RESTAURAR-HASH'"


def _escapar(valor) -> str:
    """Un valor de MySQL como texto de INSERT.

    `None` → NULL. Los números vancrudos. Todo lo demás entre comillas con el
    backslash escapado y la comilla simple doblada, que es lo que MySQL
    entiende.
    """
    if valor is None:
        return "NULL"
    if isinstance(valor, (int, float)):
        return str(valor)
    if isinstance(valor, datetime):
        return "'" + valor.strftime("%Y-%m-%d %H:%M:%S") + "'"
    if isinstance(valor, date):
        return "'" + valor.isoformat() + "'"
    texto = str(valor)
    if texto == "":
        return "''"
    return "'" + texto.replace("\\", "\\\\").replace("'", "''") + "'"


def escribir(conn, tablas, destino) -> tuple[str, int]:
    """Escribe los INSERT de las tablas dadas. Devuelve (archivo, filas).

    El archivo sale con `SET FOREIGN_KEY_CHECKS = 0`, así que el orden de las
    tablas no importa para restaurar: MySQL acepta los INSERT en cualquier
    orden y después se enciende el chequeo.
    """
    total = 0
    lineas = [
        f"-- Respaldo completo del estudio contable — {datetime.now():%Y-%m-%d %H:%M:%S}",
        "-- Para restaurar:",
        "--   C:\\xampp\\mysql\\bin\\mysql.exe -u root gestion_contable < este_archivo.sql",
        "--",
        "-- Lo generó respaldar_todo.py. Sin contraseñas (columna password_hash).",
        "",
        "SET FOREIGN_KEY_CHECKS = 0;",
        "",
    ]

    for tabla in tablas:
        filas = conn.execute(text(f"SELECT * FROM {tabla}")).mappings().all()
        if not filas:
            lineas.append(f"-- {tabla}: vacía")
            continue

        columnas = list(filas[0].keys())
        columnas_sql = ", ".join(f"`{c}`" for c in columnas)

        lineas.append(f"-- ---------- {tabla}: {len(filas)} fila(s)")
        for fila in filas:
            valores = ", ".join(
                HASH_DE_RELLENO if c in COLUMNAS_SECRETAS else _escapar(fila[c])
                for c in columnas
            )
            lineas.append(
                f"INSERT INTO `{tabla}` ({columnas_sql}) VALUES ({valores});"
            )
        if columnas_secreta := COLUMNAS_SECRETAS.intersection(columnas):
            lineas.append(
                f"-- (en {tabla} se reemplazó "
                f"{', '.join(sorted(columnas_secreta))} por un marcador)"
            )
        total += len(filas)
        lineas.append("")

    lineas.append("SET FOREIGN_KEY_CHECKS = 1;")
    lineas.append("")

    nombre = f"respaldo_{date.today().isoformat()}.sql"
    ruta = os.path.join(destino, nombre)
    i = 0
    while os.path.exists(ruta):
        i += 1
        ruta = os.path.join(destino, f"respaldo_{date.today().isoformat()}_{i}.sql")

    with open(ruta, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas))
    return os.path.basename(ruta), total


def main() -> None:
    destino = (
        sys.argv[sys.argv.index("--destino") + 1]
        if "--destino" in sys.argv
        else os.path.dirname(os.path.abspath(__file__))
    )

    with engine.connect() as conn:
        # TODAS las tablas de la base, sin lista escrita a mano: si el sistema
        # crece y aparece una tabla nueva, el respaldo la agarra sola. Ver la
        # nota de COLUMNAS_SECRETAS.
        tablas = [
            r[0]
            for r in conn.execute(
                text("SELECT TABLE_NAME FROM information_schema.TABLES "
                     "WHERE TABLE_SCHEMA = DATABASE() ORDER BY TABLE_NAME")
            ).all()
        ]
        nombre, filas = escribir(conn, tablas, destino)

    print(f"Respaldo: {nombre} ({filas} filas, {len(tablas)} tablas)")
    print(f"Carpeta:  {destino}")
    print("Para verificar que se restaura bien:  python -X utf8 probar_respaldo.py")
    print("Ojo: las contraseñas NO van en el respaldo. Si lo restaurás, hay que")
    print("     volver a ponerlas (o entrar como admin y cambiarlas).")


if __name__ == "__main__":
    main()