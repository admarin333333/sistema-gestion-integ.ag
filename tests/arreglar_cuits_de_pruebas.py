"""Cambia los CUITs de prueba por unos válidos (dígito verificador correcto).

Los números inventados que usaban las pruebas ("30-88888888-5" etc.) no
cerraban el dígito verificador, así que al activar la validación real de CUIT
la API los rechazaba. Este script los reemplaza por los equivalentes válidos.

Uso:  python -X utf8 arreglar_cuits_de_pruebas.py
"""

import io
import os
import sys

CARPETA = r"C:\Users\admar\AppData\Local\Temp\opencode"
sys.path.insert(0, _RUTA_BACKEND)

from app.schemas.persona import cuit_es_valido, digito_verificador_cuit
import os
import sys

# El backend, calculado desde donde esta este archivo: asi el proyecto
# se puede mover de carpeta sin romper los tests.
_RUTA_BACKEND = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
)

PESOS = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)


def digitos(v):
    return "".join(c for c in v if c.isdigit())


def corregir(cuit):
    d = digitos(cuit)
    if len(d) != 11:
        return None
    if cuit_es_valido(cuit):
        return cuit
    base = f"{d[:2]}{int(d[2:10]):08d}"
    dv = digito_verificador_cuit(base)
    if dv is not None:
        nuevo = f"{base[:2]}-{base[2:]}-{dv}"
        return nuevo if cuit_es_valido(nuevo) else None
    # el resto da 1: no hay verificador, se prueba con el DNI siguiente
    for salto in range(1, 300):
        n = (int(d[2:10]) + salto) % 10**8
        b = f"{d[:2]}{n:08d}"
        dv = digito_verificador_cuit(b)
        if dv is not None:
            return f"{b[:2]}-{b[2:]}-{dv}"
    return None


def mapeo():
    """Todos los CUITs que aparecen en los tests y su versión válida."""
    import re

    patron = re.compile(r"\b\d{2}-\d{8}-\d\b")
    vistos = {}
    for nombre in sorted(os.listdir(CARPETA)):
        if not nombre.startswith("test_") or not nombre.endswith(".py"):
            continue
        ruta = os.path.join(CARPETA, nombre)
        texto = io.open(ruta, encoding="utf-8").read()
        for m in patron.findall(texto):
            vistos.setdefault(m, [])
            vistos[m].append(nombre)
    return vistos


def main():
    print("CUIT que aparecen en las pruebas:\n")
    cambios = {}
    for cuit, archivos in sorted(mapeo().items()):
        nuevo = corregir(cuit)
        cambios[cuit] = nuevo
        estado = "OK   " if cuit_es_valido(cuit) else "MAL  "
        destino = nuevo if nuevo else "(sin corrección posible)"
        print(f"  {estado} {cuit:<16} -> {destino:<16} {', '.join(sorted(set(archivos)))}")

    aplicables = {k: v for k, v in cambios.items() if v and v != k}
    if not aplicables:
        print("\nNo hay nada que corregir.")
        return

    print("\nReemplazando en los archivos...")
    for nombre in sorted(os.listdir(CARPETA)):
        if not nombre.startswith("test_") or not nombre.endswith(".py"):
            continue
        ruta = os.path.join(CARPETA, nombre)
        texto = io.open(ruta, encoding="utf-8").read()
        original = texto
        for viejo, nuevo in aplicables.items():
            texto = texto.replace(viejo, nuevo)
        if texto != original:
            io.open(ruta, "w", encoding="utf-8").write(texto)
            print(f"  {nombre}")

    print("\nListo. Los CUITs inventados quedaron con verificador válido.")


if __name__ == "__main__":
    main()