"""Corre todas las suites de una y tira un resumen al final.

El backend tiene que estar levantado (puerto 8010). Si no está, avisa y
termina en vez de largar 19 tracebacks.

Uso:  python -X utf8 correr_todas.py
      python -X utf8 correr_todas.py --solo motor    (filtra por nombre)
"""

import os
import re
import subprocess
import sys

CARPETA = os.path.dirname(os.path.abspath(__file__))
# Para que `import borrar_prueba` y `from app.database import ...` funcionen:
# el helper está acá al lado y la app vive un nivel arriba, en `backend/`.
sys.path.insert(0, CARPETA)
sys.path.insert(0, os.path.join(os.path.dirname(CARPETA), "backend"))

# ------------------------------------------------------------------
# A qué base se conectan las pruebas
# ------------------------------------------------------------------
#
# Las pruebas hablan con la API de DOS maneras, y es lo que hace que la base de
# pruebas sirva:
#
#   1. Por HTTP, a la API (el 90%). Acá importa `GC_BASE_URL`: 8010 es el
#      estudio, 8011 es la base de pruebas.
#   2. Por SQL directo, con `from app.database import SessionLocal`. Se usa para
#      limpiar (la API no borra un asiento contabilizado: `asiento_origen` es
#      ON DELETE RESTRICT), para la huella digital y para verificar cosas que la
#      API no expone. Acá importa `DB_NAME`.
#
# Con solo `GC_BASE_URL` las pruebas quedaban PARTIDAS: la API en una base y el
# SQL en otra. Lo que pasaba en la práctica es que una suite creaba un recibo por
# HTTP en `gestion_contable_test` y después lo buscaba por SQL en
# `gestion_contable`, donde no existía: `Rechazo("El recibo no existe")` y la
# suite se caía. Una de cada tres.
#
# Por eso, si `GC_BASE_URL` está puesta, se supone `DB_NAME` también. Sin
# `GC_BASE_URL` no se toca nada: es la forma de siempre (8010 y la base del
# estudio), que es como se corrían las pruebas antes de esto.
BASE = os.environ.get("GC_BASE_URL", "http://127.0.0.1:8010")
NOMBRE_PRUEBA = os.environ.get("GC_TEST_DB", "gestion_contable_test")
BASE_REAL = "gestion_contable"

if "GC_BASE_URL" in os.environ:
    if NOMBRE_PRUEBA == BASE_REAL:
        raise SystemExit(
            f"Me freno: apuntás las pruebas a la base REAL ({BASE_REAL}).\n"
            "Las pruebas borran filas. Elegí otra con GC_TEST_DB."
        )
    # Va ANTES de cualquier import de `app.database`: ese módulo lee el entorno
    # una sola vez, al importarse, y después el nombre llega tarde.
    os.environ["DB_NAME"] = NOMBRE_PRUEBA
else:
    NOMBRE_PRUEBA = BASE_REAL

# Los tres formatos de resumen que usan las suites:
#   "28 OK / 0 fallos"  ·  "56/56 pruebas correctas"  ·  "RESULTADO: 60 OK, 0 fallos"
RE_OK_FALLOS = re.compile(r"(\d+)\s+OK\s*/\s*(\d+)\s+fallos")
RE_OK_FALLOS2 = re.compile(r"RESULTADO:\s*(\d+)\s+OK,\s*(\d+)\s+fallos")
RE_TODO_BIEN = re.compile(r"(\d+)\s*/\s*\d+\s+pruebas (?:correctas|pasaron)")

# Una suite que avisó que le faltan datos (`datos_de_prueba.py`) sale con código 0
# y este aviso. NO es lo mismo que "no terminó bien": acá la suite decidió no
# correr porque la base no tiene con qué, y dijo qué le falta.
#
# Antes, estas cuatro aparecían en la lista de "sin medir", que es la misma
# columna donde caen las suites que se rompen por un bug. Mezclarlas hacía que
# una omisión—a propósito— se leyera como un problema del programa.
RE_OMITIDA = re.compile(r"SUITE OMITIDA: faltan datos de prueba")


def backend_arriba() -> bool:
    import urllib.request

    try:
        urllib.request.urlopen(f"{BASE}/docs", timeout=5)
        return True
    except Exception:
        return False


def correr(archivo: str) -> tuple[int, str]:
    """Devuelve (pruebas, fallos) de una suite. -1 si no se pudo medir."""
    proc = subprocess.run(
        [sys.executable, "-X", "utf8", archivo],
        cwd=CARPETA,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    salida = proc.stdout + proc.stderr

    # Omitida a propósito: se mide 0/0 y se marca aparte. Se chequea ANTES de
    # buscar un resumen, porque una suite omitida no tiene ninguno.
    if RE_OMITIDA.search(salida):
        return 0, 0

    for linea in reversed(salida.split("\n")):
        # "28 OK / 0 fallos" o "RESULTADO: 60 OK, 0 fallos"
        m = RE_OK_FALLOS.search(linea) or RE_OK_FALLOS2.search(linea)
        if m:
            return int(m.group(1)), int(m.group(2))
        # "56/56 pruebas correctas" -> todo bien, 0 fallos
        m = RE_TODO_BIEN.search(linea)
        if m:
            return int(m.group(1)), 0
    return -1, 0


def limpiar_raros() -> None:
    """Llama al limpiador del backend antes de empezar.

    Los tests crean clientes con CUIT fijo. Si una corrida se corta a mitad,
    quedan colgados con sus facturas Y sus asientos, y la corrida siguiente
    falla con "Ya existe Factura B 0001-00000042" o "El recibo ya tenía
    asiento". Limpiar antes evita estar limpiando a mano cada vez.

    Los datos REALES del usuario no se tocan: el limpiador solo borra personas
    cuyo CUIT o DNI esté en la lista de pruebas (39888777, 39777666, etc.).
    """
    import subprocess

    scripts = [
        os.path.join(os.path.dirname(CARPETA), "backend", "limpiar_clientes_prueba.py"),
        # Los recibos con asiento no se pueden borrar por la API (asiento_origen
        # es ON DELETE RESTRICT), así que esa suite limpia por SQL.
        os.path.join(CARPETA, "limpiar_prueba_recibo_pagos.py"),
    ]
    for script in scripts:
        if not os.path.exists(script):
            continue
        proc = subprocess.run(
            [sys.executable, "-X", "utf8", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        salida = (proc.stdout or "") + (proc.stderr or "")
        if "no hay nada que limpiar" in salida.lower():
            print("  Base limpia: no hay restos de corridas anteriores.")
            return
        for linea in salida.split("\n"):
            if "Borrados" in linea or "Respaldo" in linea or "limpiado" in linea:
                print("  " + linea.strip())


def respaldo_completo() -> None:
    """Saca un respaldo de TODO antes de tocar nada.

    Las suites limpian por SQL (la API, bien hecha, no borra un asiento
    contabilizado), y el 02/10/2026 eso costó caro: siete suites hacían
    `DELETE FROM asientos` a secas y se llevaron los asientos reales, sin
    respaldo de nada. Ver AGENTE.md §6 bis.
    """
    import subprocess

    script = os.path.join(CARPETA, "respaldar_todo.py")
    if not os.path.exists(script):
        return
    proc = subprocess.run(
        [sys.executable, "-X", "utf8", script],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    for linea in (proc.stdout or "").split("\n"):
        if linea.strip().startswith("Respaldo"):
            print("  " + linea.strip())


def huella():
    """Las filas reales de la base, por tabla. Para comparar al terminar."""
    import borrar_prueba
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        return borrar_prueba.huella(db)
    finally:
        db.close()


def main():
    filtro = ""
    if "--solo" in sys.argv:
        filtro = sys.argv[sys.argv.index("--solo") + 1].lower()

    if not backend_arriba():
        print(f"El backend no está levantado en {BASE}.")
        print("Levantalo primero:")
        print("  cd backend")
        print("  python -m uvicorn app.main:app --host=127.0.0.1 --port=8010")
        raise SystemExit(1)

    suites = sorted(
        f for f in os.listdir(CARPETA)
        if f.startswith("test_") and f.endswith(".py")
        and filtro in f.lower()
    )
    if not suites:
        print(f"Ninguna suite coincide con «{filtro}»")
        raise SystemExit(1)

    print(f"Correndo {len(suites)} suite(s)")
    respaldo_completo()
    limpiar_raros()
    antes = huella()
    print("=" * 52)

    total_ok = 0
    total_fallos = 0
    sin_medir = []
    omitidas = []

    for nombre in suites:
        ok, fallos = correr(nombre)
        if ok == 0 and fallos == 0:
            # Podría ser una suite sin pruebas, así que se confirma leyendo la
            # salida: si dice "SUITE OMITIDA", fue a propósito.
            omitidas.append(nombre)
            print(f"  --  {nombre:<30} omitida (faltan datos de prueba)")
            continue
        if ok < 0:
            sin_medir.append(nombre)
            print(f"  ??  {nombre:<30} no terminó bien (revisar a mano)")
            continue
        total_ok += ok
        total_fallos += fallos
        marca = "OK " if fallos == 0 else "FALLA"
        print(f"  {marca} {nombre:<30} {ok} pruebas, {fallos} fallos")

    print("=" * 52)

    # --- la huella digital: ¿se perdieron datos reales? -----------------
    #
    # Esta es la prueba que faltaba el 02/10/2026. Las suites dan verde
    # aunque se coman un asiento real, porque miden diferencias contra su
    # propia línea de base. Acá se mide lo que NO es de la suite: si una fila
    # que el contador cargó ya no está, la corrida falla y dice cuál.
    import borrar_prueba

    perdidas = borrar_prueba.comparar(antes, huella())
    if perdidas:
        total_fallos += len(perdidas)
        print()
        print("  ⛔ SE PERDIERON DATOS REALES (esto es un bug de las pruebas):")
        for linea in perdidas:
            print(f"     - {linea}")
        print("     Los tests no pueden borrar nada que no sea de prueba.")
        print("     Revisá la suite que las borró (AGENTE.md §6 bis).")
    else:
        print("  Huella digital: ninguna fila real se perdió.")

    if sin_medir:
        print(f"  {len(sin_medir)} suite(s) sin medir: {', '.join(sin_medir)}")

    # Las omitidas van aparte de las sin medir. Una suite omitida avisó que le
    # faltan datos y decidió no correr: no es un problema del programa, así que
    # no vuelve rojo el resultado. Igual se listan, porque si nadie las mira
    # después se olvidan.
    if omitidas:
        print()
        print(f"  {len(omitidas)} suite(s) OMITIDAS por falta de datos de prueba:")
        for nombre in omitidas:
            print(f"     - {nombre}")
        print("     No es un fallo del programa. Para ver el detalle de qué falta,")
        print("     corré esa suite sola; dice exactamente qué le falta.")

    print()
    print(f"  TOTAL: {total_ok} pruebas, {total_fallos} fallos")

    if total_fallos or sin_medir:
        raise SystemExit(1)
    print("  Todo en verde.")


if __name__ == "__main__":
    main()