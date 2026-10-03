"""Mueve las fechas del test del motor contable dentro del ejercicio del estudio.

Desde el 02/10/2026 los comprobantes internos numeran POR EJERCICIO, y el
ejercicio de esta empresa va del 01/09/2026 al 31/08/2027. El test usaba fechas
de marzo y abril de 2026, que ahora quedan fuera y el backend las rechaza (que
es lo correcto: un comprobante guardado en el ejercicio equivocado después no
se puede arreglar).

Uso:  python -X utf8tests\arreglar_fechas_motor.py
"""

import io
import os

RUTA = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "test_motor_contable.py")

# Las tres fechas que estaban fuera del ejercicio, con su equivalente adentro.
CAMBIOS = [
    ('"fecha": "2026-03-01"', '"fecha": "2026-09-10"'),
    ('"fecha": "2026-03-05"', '"fecha": "2026-09-05"'),
    ('"fecha": "2026-04-01"', '"fecha": "2026-09-20"'),
]


def main():
    with io.open(RUTA, "r", encoding="utf-8") as f:
        texto = f.read()

    total = 0
    for viejo, nuevo in CAMBIOS:
        cantidad = texto.count(viejo)
        texto = texto.replace(viejo, nuevo)
        total += cantidad
        print(f"  {cantidad} x {viejo} -> {nuevo}")

    if total == 0:
        print("No quedó ninguna fecha fuera del ejercicio")
        return

    with io.open(RUTA, "w", encoding="utf-8") as f:
        f.write(texto)
    print(f"\n{total} fechas movidas dentro del ejercicio")


if __name__ == "__main__":
    main()