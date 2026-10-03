"""Prueba de fuego del respaldo: restaurarlo en una base VACÍA y comparar.

Un `.sql` que no se pudo restaurar no es un respaldo, es un archivo con texto.
Esta script lo verifica de punta a punta:

1. Crea una base nueva y vacía (`respaldo_test`).
2. Le copia la **estructura** de la base real (las tablas, sin datos).
3. Restaura adentro el `.sql` que generó `respaldar_todo.py`.
4. Compara fila por fila: si alguna tabla tiene un número distinto de filas, o
   el contenido no calza, la prueba falla.

No toca la base del estudio: escribe solo en `respaldo_test`, que se borra al
terminar.

Uso:  python -X utf8 probar_respaldo.py
"""

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

import pymysql  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import engine  # noqa: E402

BASE_ORIGEN = settings.db_name
BASE_PRUEBA = "respaldo_test"


def conexion(base):
    return pymysql.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=base,
        charset="utf8mb4",
        autocommit=True,
    )


def tablas_de(conn, base):
    with conn.cursor() as c:
        c.execute(
            "SELECT TABLE_NAME FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = %s",
            (base,),
        )
        return [r[0] for r in c.fetchall()]


def separar_sentencias(sql: str):
    """Parte el archivo en sentencias.

    Se parte por `;\n` a fin de línea, que es como el generador los escribe
    (cada INSERT termina ahí). Es bastante más simple que un parser completo y
    alcanza para este archivo, que genera una sola máquina.
    """
    sin_comentarios = re.sub(r"^\s*--.*$", "", sql, flags=re.M)
    for parte in sin_comentarios.split(";\n"):
        parte = parte.strip()
        if parte:
            yield parte + ";"


def main() -> int:
    carpeta = os.path.dirname(os.path.abspath(__file__))
    respaldos = sorted(
        f for f in os.listdir(carpeta) if f.startswith("respaldo_") and f.endswith(".sql")
    )
    if not respaldos:
        print("No hay ningún respaldo en la carpeta. Corré respaldar_todo.py.")
        return 1
    archivo = os.path.join(carpeta, respaldos[-1])
    print(f"Probando: {respaldos[-1]}")

    admin = conexion("")
    with admin.cursor() as c:
        c.execute(f"DROP DATABASE IF EXISTS {BASE_PRUEBA}")
        c.execute(
            f"CREATE DATABASE {BASE_PRUEBA} CHARACTER SET utf8mb4 "
            "COLLATE utf8mb4_unicode_ci"
        )
    print(f"  + base vacía {BASE_PRUEBA}")

    # 1) la estructura de la base real
    #
    # Las tablas se crean en el orden que devuelve `information_schema`, que NO
    # respeta las dependencias: `clientes` puede aparecer antes que `personas` y
    # el `SHOW CREATE TABLE` falla con "Failed to open the referenced table". Por
    # eso se apagan los chequeos de FK mientras se arma el esqueleto; los datos
    # también se restauran con la comprobación apagada, y al final se enciende.
    origen = conexion(BASE_ORIGEN)
    destino = conexion(BASE_PRUEBA)
    tablas = tablas_de(origen, BASE_ORIGEN)
    with destino.cursor() as cd:
        cd.execute(f"USE {BASE_PRUEBA}")
        cd.execute("SET FOREIGN_KEY_CHECKS = 0")
    for t in tablas:
        with origen.cursor() as co:
            co.execute(f"SHOW CREATE TABLE `{t}`")
            ddl = co.fetchone()[1]
        with destino.cursor() as cd:
            cd.execute(ddl)
    print(f"  = estructura de {len(tablas)} tablas copiada")

    # 2) restaurar el respaldo
    with open(archivo, "r", encoding="utf-8") as f:
        sql = f.read()
    sentencias = list(separar_sentencias(sql))
    with destino.cursor() as c:
        c.execute(f"USE {BASE_PRUEBA}")
        c.execute("SET FOREIGN_KEY_CHECKS = 0")
        for s in sentencias:
            c.execute(s)
        c.execute("SET FOREIGN_KEY_CHECKS = 1")
    print(f"  = {len(sentencias)} sentencias restauradas")

    # 3) comparar
    fallos = 0
    for t in tablas:
        with origen.cursor() as co:
            co.execute(f"SELECT COUNT(*) FROM `{t}`")
            n_real = co.fetchone()[0]
        with destino.cursor() as cd:
            cd.execute(f"SELECT COUNT(*) FROM `{t}`")
            n_prueba = cd.fetchone()[0]
        if n_real != n_prueba:
            print(f"  FALLA  {t}: real={n_real} restaurada={n_prueba}")
            fallos += 1
    print(f"  = {len(tablas)} tablas comparadas")

    # contenido, no solo cantidad: dos tablas con el mismo número de filas
    # pueden tener distinto contenido.
    for t in ("personas", "clientes", "facturas", "recibos", "asiento_detalle"):
        if t not in tablas:
            continue
        with origen.cursor() as co:
            co.execute(f"SELECT * FROM `{t}`")
            real = co.fetchall()
        with destino.cursor() as cd:
            cd.execute(f"SELECT * FROM `{t}`")
            restaurada = cd.fetchall()
        if real != restaurada:
            print(f"  FALLA  {t}: el CONTENIDO no coincide (mismas filas, distinto texto)")
            fallos += 1
    print("  = contenido comparado (personas, clientes, facturas, recibos, detalle)")

    with admin.cursor() as c:
        c.execute(f"DROP DATABASE IF EXISTS {BASE_PRUEBA}")
    print(f"  - base {BASE_PRUEBA} borrada")

    print()
    if fallos:
        print(f"  {fallos} FALLO(S): el respaldo NO sirve")
        return 1
    print("  El respaldo se restaura bien. Se puede confiar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())