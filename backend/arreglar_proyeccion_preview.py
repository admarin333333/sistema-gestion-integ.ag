"""Arregla `proyectar_venta`: usa el importe real, no el neto.

En el preview no hay factura guardada, así que el total hay que pasarlo
explícitamente. Antes usaba una función auxiliar que devolvía cero, lo que
rompía la proyección cuando no hay IVA desglosado.

No cambia datos ni lógica: solo deja de usar el placeholder.

Uso:  python -X utf8 backend/arreglar_proyeccion_preview.py
"""

import io
import os

RUTA = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "app", "services", "asiento_automatico.py",
)

VIEJO = "_importe_total(neto, iva, fecha)"


def main():
    with io.open(RUTA, "r", encoding="utf-8") as f:
        texto = f.read()

    if VIEJO not in texto:
        print("No encontré el placeholder: no se toca nada.")
        return

    texto = texto.replace(VIEJO, "importe")

    # La función auxiliar ya no se usa: se borra entera.
    ini = texto.find("def _importe_total(")
    if ini >= 0:
        fin = texto.find("def asiento_de_venta(", ini)
        if fin > ini:
            texto = texto[:ini] + texto[fin:]
            print("función _importe_total eliminada")

    with io.open(RUTA, "w", encoding="utf-8") as f:
        f.write(texto)
    print("proyectar_venta ahora usa el importe real")


if __name__ == "__main__":
    main()