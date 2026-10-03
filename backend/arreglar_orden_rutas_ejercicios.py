"""Mueve el bloque de cuenta-cobro-fija antes de las rutas con {ejercicio_id}.

FastAPI evalúa las rutas EN ORDEN. `PUT /ejercicios/{ejercicio_id}` se había
definido antes que `PUT /ejercicios/cuenta-cobro-fija`, así que la palabra
"cuenta-cobro-fija" entraba por la ruta del parámetro y Pydantic intentaba
leerla como número entero -> 422.

No cambia ningún datos: es orden de definición de rutas.

Uso:  python -X utf8 backend/arreglar_orden_rutas_ejercicios.py
"""

import io
import os

RUTA = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "app", "routers", "ejercicios.py"
)

MARCADOR = "# ------------------------------------------- cuenta de cobro fija (cobranza)"
ANCLA = '@router.post("", status_code=201)'


def main():
    with io.open(RUTA, "r", encoding="utf-8") as f:
        texto = f.read()

    if MARCADOR not in texto:
        print("No encontré el bloque de cuenta de cobro: no se toca nada.")
        return

    i = texto.index(MARCADOR)
    bloque = texto[i:].rstrip()
    resto = texto[:i].rstrip()

    # Ya está bien si la marca aparece ANTES del ancla en el archivo.
    if texto.index(MARCADOR) < texto.index(ANCLA):
        print("El bloque ya está antes de las rutas con {ejercicio_id}.")
        return

    j = resto.index(ANCLA)
    nuevo = resto[:j] + bloque + "\n\n\n" + resto[j:]

    with io.open(RUTA, "w", encoding="utf-8") as f:
        f.write(nuevo)
    print("Bloque cuenta-cobro-fija movido antes de las rutas con {ejercicio_id}.")


if __name__ == "__main__":
    main()