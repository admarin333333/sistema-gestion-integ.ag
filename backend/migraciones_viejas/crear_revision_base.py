"""Crea la revisión BASE de Alembic.

    python -X utf8 crear_revision_base.py

POR QUÉ HACE FALTA

Cuando se adoptó Alembic, el esquema ya estaba entero: 43 tablas hechas por 23
scripts `migrar_*.py`. La pregunta era cómo decirle a Alembic "esta base ya está
al día" **sin** generar una migración que intente recrear todo.

La respuesta es una revisión **vacía**: un archivo de migración que no hace nada,
que sirve solo para tener un punto de partida. Es el patrón estándar de "baseline"
y lo usan todos los proyectos que adoptan Alembic sobre una base que ya existe.

Después de crearla, `alembic stamp head` anota esa revisión en la tabla
`alembic_version` — **una sola fila, sin tocar el esquema**. Y a partir de ahí
todo cambio nuevo es `alembic revision --autogenerate`.

LO QUE ESTA REVISIÓN NO HACE

Nada. `upgrade()` y `downgrade()` están vacíos a propósito. No es una migración
perezosa: es el marcador de " acá ya estaba todo".

Si alguien corre `alembic upgrade head` sobre la base del estudio, esta revisión
no le hace nada y la base queda igual.

Idempotente: si la revisión ya existe, no la vuelve a hacer.
"""

import os
import subprocess
import sys

BACKEND = os.path.dirname(os.path.abspath(__file__))
VERS = os.path.join(BACKEND, "migraciones", "versions")

# El texto va con `"""` y sin acentos raros: este archivo lo ejecuta Alembic, que lo
# lee como Python normal. Los acentos van bien (UTF-8), pero el punto es que el
# contenido de la migración viaja dentro del archivo de versiones.
MENSAJE = """linea base: el esquema ya existia

Esta migracion NO hace nada. Es el punto de partida.

El esquema del estudio ya estaba armado por 23 scripts `migrar_*.py` sueltos antes
de que hubiera Alembic. Para que Alembic no proponga recrear 43 tablas que ya
existen, se crea esta revision vacia y se marca la base con `alembic stamp head`.

A partir de aca, TODO cambio de esquema va por Alembic:
    alembic revision --autogenerate -m "lo que se agrego"
    alembic upgrade head

Los `migrar_*.py` no se borran: los que cargan DATOS (el ejercicio, los periodos,
el plan de cuentas) siguen haciendo falta. Lo que cambia es que el ESQUEMA ya no
se toca con scripts sueltos.

revision_ identifiers van aparte: el archivo lo genera Alembic.
"""


def ya_existe():
    if not os.path.isdir(VERS):
        return False
    return any(n.startswith("0") or "_" in n for n in os.listdir(VERS) if n.endswith(".py"))


def main():
    if ya_existe():
        print("  Ya hay revisiones en migraciones/versions. No hago nada.")
        return

    r = subprocess.run(
        [sys.executable, "-m", "alembic", "revision", "-m",
         "linea base: el esquema ya existia"],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if r.returncode != 0:
        print("  No se pudo crear la revisión:")
        print((r.stderr or r.stdout)[-400:])
        raise SystemExit(1)

    # El archivo generado tiene un docstring con el mensaje. Se reemplaza por el
    # que explica de verdad por qué está vacía.
    nombres = [n for n in os.listdir(VERS) if n.endswith(".py")]
    if not nombres:
        print("  Alembic no creó el archivo.")
        raise SystemExit(1)
    ruta = os.path.join(VERS, nombres[0])

    with open(ruta, encoding="utf-8") as f:
        contenido = f.read()

    # Va entre el primer `"""` y el siguiente `"""`, que es el docstring del módulo.
    inicio = contenido.find('"""')
    fin = contenido.find('"""', inicio + 3)
    if inicio == -1 or fin == -1:
        print("  No se encontró el docstring para reemplazar.")
        return

    nuevo = contenido[:inicio] + '"""\n' + MENSAJE + contenido[fin:]
    with open(ruta, "w", encoding="utf-8", newline="\n") as f:
        f.write(nuevo)

    print(f"  Revisión base creada: {nombres[0]}")
    print()
    print("  Ahora sí: `alembic stamp head` marca la base como al día.")
    print("  (solo escribe una fila en alembic_version; no toca el esquema)")


if __name__ == "__main__":
    main()