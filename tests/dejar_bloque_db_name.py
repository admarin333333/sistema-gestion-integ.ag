"""Deja el bloque `DB_NAME` en el lugar correcto, una vez por suite.

    python -X utf8 dejar_bloque_db_name.py [nombre_de_suite]

POR QUÉ ESTE SCRIPT

Hay suites que hablan con la base de DOS maneras:

  - por HTTP, contra la API (`GC_BASE_URL`): 8010 es el estudio, 8011 pruebas
  - por SQL directo, con `app.database`: para limpiar, para la huella, para
    verificar cosas que la API no expone

Con solo `GC_BASE_URL` el SQL se va a la base REAL: la limpieza no borra nada de
la base de pruebas, los documentos que la suite crea no desaparecen, y la
corrida siguiente falla con "Ya existe Factura B 0001-00099991".

Por eso hace falta `DB_NAME`. Y tiene que estar puesta ANTES de importar
`app.database`, porque ese módulo lee el entorno UNA sola vez al importarse.

DÓNDE VA EL BLOQUE

En el nivel del módulo, justo antes del primer `from app.database`. No adentro de
la función que limpia: ahí corre más tarde y para entonces `app.database` ya se
importó con la base equivocada.

CÓMO LO HACE

1. Tira el bloque anterior y sus restos (incluido el `)` que queda pegado si el
   bloque estaba partido).
2. Inserta el bloque limpio en el punto correcto.
3. Compila el archivo. Si no compila, RESTAURA el original y avisa.

Idempotente: la segunda vez no cambia nada.

LO QUE NO HACE

No reescribe imports ni mueve código. Solo saca lo suyo y pone lo suyo. Si algo
más está roto, lo dice y no lo toca.
"""

import io
import os
import re
import subprocess
import sys

CARPETA = r"C:\proyecto-gestion-contable\tests"

INICIO = 'if "GC_BASE_URL" in os.environ:'
LINEA_DB_NAME = '"DB_NAME", os.environ.get("GC_TEST_DB", "gestion_contable_test")'
COMENTARIOS = (
    "# Esta suite habla con la base de DOS maneras",
    "# `GC_BASE_URL`",
    "# `DB_NAME`",
    "# se va a la base REAL",
    "# arriba del archivo",
    "# (`app.database`",
)

BLOQUE = f'''# Esta suite habla con la base de DOS maneras: por HTTP (`BASE`) y por SQL
# directo (`app.database`, para limpiar lo que dejó la corrida). Con solo
# `GC_BASE_URL` el SQL se va a la base REAL y la limpieza no borra nada de la base
# de pruebas.
#
# `DB_NAME` tiene que estar puesta ANTES de que se importe `app.database`, porque
# ese módulo lee el entorno UNA sola vez al importarse. Por eso este bloque va
# arriba del archivo, en el nivel del módulo, y no adentro de la función que
# limpia.
{INICIO}
    os.environ.setdefault(
        {LINEA_DB_NAME}
    )
'''


def es_del_bloque(linea):
    """¿Esta línea es del bloque `DB_NAME` o de sus restos?"""
    s = linea.strip()
    if s in (INICIO, LINEA_DB_NAME, "os.environ.setdefault(", ")"):
        return True
    return any(c in linea for c in COMENTARIOS)


def sacar_bloque(lineas):
    """
    Saca el bloque y sus restos.

    Importante: solo saca líneas mientras está EN el bloque. Un `)` suelto en
    medio del archivo puede ser código de verdad (el cierre de una llamada), así
    que no se puede borrar "todo lo que sea `)`".

    El bloque empieza en `INICIO` o en el comentario que lo precede, y termina
    dos líneas después de `LINEA_DB_NAME` (el `os.environ.setdefault(` y el
    cierre). Si aparecen varios, se sacan todos.
    """
    fuera = []
    i = 0
    while i < len(lineas):
        if lineas[i].strip() == INICIO:
            # Retroceder sobre el comentario que lo acompaña.
            ini = i
            while ini > 0 and lineas[ini - 1].lstrip().startswith("#"):
                ini -= 1
            # Adelante hasta pasar la línea con DB_NAME y su cierre.
            j = i
            while j < len(lineas) and LINEA_DB_NAME not in lineas[j]:
                j += 1
            j += 1                      # la línea del DB_NAME
            while j < len(lineas):
                j += 1                  # la línea del ")"
                if lineas[j - 1].rstrip().endswith(")"):
                    break
            # Comer la línea en blanco que quedó pegada abajo.
            while j < len(lineas) and lineas[j].strip() == "":
                j += 1
            # Dejar una sola línea en blanco donde estaba.
            del lineas[ini:j]
            fuera.append("")
            continue

        # Restos: comentarios del bloque, o el `)` y el setdefault partidos.
        if any(c in lineas[i] for c in COMENTARIOS) or (
            lineas[i].strip() in ("os.environ.setdefault(", LINEA_DB_NAME)
        ):
            i += 1
            continue

        fuera.append(lineas[i])
        i += 1

    return fuera


def arriba_del_archivo(lineas):
    """Después de los imports y de `BASE = ...`, en el nivel del módulo."""
    ultimo = 0
    for i, l in enumerate(lineas):
        if re.match(r"\s*(import |from .+ import |sys\.path\.insert)", l):
            ultimo = i + 1
    for i in range(ultimo, min(ultimo + 8, len(lineas))):
        if re.match(r"\s*BASE\s*=", lineas[i]):
            return i + 1
    return ultimo


def primer_import_app(lineas):
    """
    El índice del PRIMER `from app.database` que esté en el NIVEL DEL MÓDULO.

    Importante: tiene que estar en la columna 0.

    Hay suites donde el `app.database` aparece por primera vez DENTRO de una
    función de limpieza, con sangría:

        def borrar_asientos(token, ids):
            ...
            from app.database import SessionLocal

    Ahí el bloque NO va: quedaría dentro de la función, que corre más tarde, y
    para entonces `app.database` ya se importó con la base equivocada. Y el
    archivo tampoco compila, porque el bloque se cuela entre el `from
    sqlalchemy import text` y el código que le sigue con sangría.

    En esas suites el bloque va arriba del archivo, después de los imports.

    Lo que pasó hoy: la primera versión de este script tomaba ese import con
    sangría como si fuera válido, y 3 suites quedaron partidas.
    """
    hay_con_sangria = False
    for i, l in enumerate(lineas):
        if re.match(r"^\s*(from app\.database import|import app\.database)", l):
            if l[0] not in " \t":       # columna 0
                return i
            hay_con_sangria = True

    if hay_con_sangria:
        return arriba_del_archivo(lineas)
    return None


def main():
    solo = sys.argv[1] if len(sys.argv) > 1 else None
    cambiados = 0
    problemas = []

    for nombre in sorted(os.listdir(CARPETA)):
        if not (nombre.startswith("test_") and nombre.endswith(".py")):
            continue
        if solo and solo not in nombre:
            continue

        ruta = os.path.join(CARPETA, nombre)
        original = io.open(ruta, encoding="utf-8").read()
        if "GC_BASE_URL" not in original or "app.database" not in original:
            continue

        limpios = sacar_bloque(original.split("\n"))
        texto_limpio = "\n".join(limpios)

        if not re.search(r"^import os$", texto_limpio, re.M):
            problemas.append((nombre, "no importa os"))
            continue

        pos = primer_import_app(limpios)
        if pos is None:
            problemas.append((nombre, "no import de app.database"))
            continue

        nuevo = "\n".join(limpios[:pos] + BLOQUE.split("\n") + limpios[pos:])
        if nuevo == original:
            print(f"  =  {nombre:36} ya estaba bien")
            continue

        io.open(ruta, "w", encoding="utf-8", newline="\n").write(nuevo)

        r = subprocess.run(
            [sys.executable, "-m", "py_compile", ruta],
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            io.open(ruta, "w", encoding="utf-8", newline="\n").write(original)
            problemas.append((nombre, "no compilaba, restaurado"))
            print(f"  !  {nombre:36} no compilaba. Restaurado.")
            continue

        cambiados += 1
        print(f"  ok {nombre:36} bloque en la L{pos + 1}")

    print()
    for nombre, motivo in problemas:
        print(f"  -  {nombre:36} {motivo}")
    print(f"  {cambiados} suite(s) corregidas, {len(problemas)} sin tocar.")


if __name__ == "__main__":
    main()
