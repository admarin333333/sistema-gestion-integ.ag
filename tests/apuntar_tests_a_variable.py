"""Hace que las suites lean la URL de la API de una variable de entorno.

    python -X utf8 apuntar_tests_a_variable.py

**Qué cambia.** 32 de las 40 suites tenían la dirección de la API escrita de
corduño:

    BASE = "http://127.0.0.1:8010"

Eso las ata a un puerto y a una base: no hay forma de corrirlas contra la base de
pruebas sin editar los 32 archivos a mano. Con esto pasan a ser:

    BASE = os.environ.get("GC_BASE_URL", "http://127.0.0.1:8010")

Es **retrocompatible**: si la variable no está, usan 8010 y siguen funcionando
exacto como antes. No hay que cambiar cómo se corren.

**Idempotente:** corre las veces que haga falta. Si un archivo ya está
convertido, lo deja quieto.

**No toca nada más:** solo esa línea. Lo demás del archivo queda como estaba.
"""

import os
import re

CARPETA = os.path.dirname(os.path.abspath(__file__))

VIEJA = re.compile(
    r'^(?P<sangria>\s*)BASE\s*=\s*"http://127\.0\.0\.1:8010"\s*$',
    re.M,
)

NUEVA = (
    '# La dirección de la API sale de `GC_BASE_URL` para poder correr estas pruebas\n'
    '# contra la base de PRUEBAS y no contra la del estudio. Si la variable no\n'
    '# está, usa 8010 como antes: no cambia cómo se corren.\n'
    '{sangria}BASE = os.environ.get("GC_BASE_URL", "http://127.0.0.1:8010")'
)


def tiene_os(path):
    with open(path, encoding="utf-8") as f:
        return re.search(r"^import os\s*$", f.read(), re.M) is not None


def agregar_import_os(texto):
    """ mete `import os` arriba de todo, si no está.

    Va antes del primer `import` que ya haya. Si no hubiera ninguno (no pasa),
    se agrega al principio.
    """
    if re.search(r"^import os\s*$", texto, re.M):
        return texto
    m = re.search(r"^(?:import |from )", texto, re.M)
    if not m:
        return "import os\n\n" + texto
    return texto[: m.start()] + "import os\n" + texto[m.start():]


def main():
    convertidos = []
    ya_estaban = []

    for nombre in sorted(os.listdir(CARPETA)):
        if not nombre.startswith("test_") or not nombre.endswith(".py"):
            continue
        ruta = os.path.join(CARPETA, nombre)

        with open(ruta, encoding="utf-8") as f:
            texto = f.read()

        if 'os.environ.get("GC_BASE_URL"' in texto:
            ya_estaban.append(nombre)
            continue

        m = VIEJA.search(texto)
        if not m:
            continue

        texto = VIEJA.sub(NUEVA.format(sangria=m.group("sangria")), texto)
        texto = agregar_import_os(texto)

        with open(ruta, "w", encoding="utf-8", newline="\n") as f:
            f.write(texto)
        convertidos.append(nombre)

    print(f"  convertidos: {len(convertidos)}")
    for n in convertidos:
        print(f"    + {n}")
    if ya_estaban:
        print(f"  ya estaban convertidos: {len(ya_estaban)}")

    quedan = []
    for nombre in sorted(os.listdir(CARPETA)):
        if nombre.startswith("test_") and nombre.endswith(".py"):
            ruta = os.path.join(CARPETA, nombre)
            with open(ruta, encoding="utf-8") as f:
                if 'os.environ.get("GC_BASE_URL"' not in f.read():
                    quedan.append(nombre)

    print()
    if quedan:
        print("  SIN convertir (revisar a mano):")
        for n in quedan:
            print(f"    ? {n}")
    else:
        print("  Todas las suites leen GC_BASE_URL.")


if __name__ == "__main__":
    main()