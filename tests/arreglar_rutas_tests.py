"""Hace relativas las rutas al backend que tenían los tests.

Estaban escritas como r"C:\\proyecto-gestion-contable\\backend", o sea que si
el proyecto se movía de carpeta, los tests que talkean con la base (limpiar
restos, romper un asiento a propósito) dejaban de andar.

Se reemplaza SOLO el pedazo de la ruta, dejando las comas y los paréntesis que
ya estaban:

    sys.path.insert(0, r"C:\\proyecto-gestion-contable\\backend")
    ->  sys.path.insert(0, _RUTA_BACKEND)

Uso:  python -X utf8 arreglar_rutas_tests.py
"""

import io
import os

CARPETA = os.path.dirname(os.path.abspath(__file__))

# El texto exacto que se busca y el que se pone en su lugar.
VIEJO = 'r"C:\\proyecto-gestion-contable\\backend"'
VIEJO_PLANTILLAS = 'r"C:\\proyecto-gestion-contable\\backend\\plantillas"'

NUEVO_PLANTILLAS = 'os.path.join(_RUTA_BACKEND, "plantillas")'
NUEVO = "_RUTA_BACKEND"

# El bloque que se inserta arriba del archivo.
CABECERA = (
    "import os\n"
    "import sys\n"
    "\n"
    "# El backend, calculado desde donde esta este archivo: asi el proyecto\n"
    "# se puede mover de carpeta sin romper los tests.\n"
    "_RUTA_BACKEND = os.path.normpath(\n"
    '    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")\n'
    ")\n"
)


def main():
    cambiados = []
    for nombre in sorted(os.listdir(CARPETA)):
        if not nombre.endswith(".py") or nombre == os.path.basename(__file__):
            continue

        ruta = os.path.join(CARPETA, nombre)
        with io.open(ruta, "r", encoding="utf-8") as f:
            texto = f.read()

        if "proyecto-gestion-contable" not in texto:
            continue

        # Primero plantillas (que es la cadena más larga y contiene a la otra).
        texto = texto.replace(VIEJO_PLANTILLAS, NUEVO_PLANTILLAS)
        texto = texto.replace(VIEJO, NUEVO)

        # La cabecera va arriba del todo, después de la línea de imports que
        # ya hubiera (si los hay, se dejan donde están y la cabecera va
        # después, que es lo que necesita el código que la usa).
        lineas = texto.split("\n")
        # Se busca dónde termina el bloque de imports inicial.
        ultimo_import = -1
        for i, linea in enumerate(lineas[:40]):
            if linea.startswith(("import ", "from ")) or linea.startswith(
                ("    ", "\t")
            ) and ("import" in linea or linea.rstrip().endswith(",")):
                ultimo_import = i
        corte = ultimo_import + 1 if ultimo_import >= 0 else 0
        texto = (
            "\n".join(lineas[:corte]) + "\n" + CABECERA + "\n".join(lineas[corte:])
        )

        with io.open(ruta, "w", encoding="utf-8") as f:
            f.write(texto)
        cambiados.append(nombre)

    print("Archivos con rutas relativas:")
    for n in cambiados:
        print("  " + n)
    print(f"\n{len(cambiados)} archivos")


if __name__ == "__main__":
    main()