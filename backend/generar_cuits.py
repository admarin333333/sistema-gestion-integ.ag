"""Calcula CUITs válidos para usar en las pruebas.

Un CUIT válido = prefijo (20/23/24/27/30/33/34) + 8 dígitos + el dígito
verificador (módulo 11, norma ARCA). Los números inventados que se usaban en
las pruebas no cerraban el verificador, así que hay que recalcularlo.

Uso:  python -X utf8 generar_cuits.py [cantidad]
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.schemas.persona import cuit_es_valido, digito_verificador_cuit

PREFIJOS_PERSONAS = ("20", "23", "24", "27", "30", "33", "34")


def cuit_de_numeros(prefijo: str, numero: int) -> str | None:
    """Arma el CUIT de un prefijo y un número de DNI de 8 dígitos.

    Devuelve None si con ese número no existe verificador (resto 1).
    """
    base = f"{prefijo}{numero:08d}"
    dv = digito_verificador_cuit(base)
    if dv is None:
        return None
    cuit = f"{base[:2]}-{base[2:10]}-{dv}"
    return cuit if cuit_es_valido(cuit) else None


def cuit_valido_para(prefijo: str, numero: int, intentos: int = 200) -> str | None:
    """Como `cuit_de_numeros`, pero prueba números cercanos si ese no cierra."""
    for salto in range(intentos):
        n = (numero + salto) % 10**8
        cuit = cuit_de_numeros(prefijo, n)
        if cuit:
            return cuit
    return None


def corregir(cuit: str) -> str | None:
    """Si el CUIT no cierra, devuelve uno válido con el mismo prefijo y DNI."""
    d = "".join(c for c in cuit if c.isdigit())
    if len(d) != 11:
        return None
    if cuit_es_valido(cuit):
        return cuit
    base = f"{d[:2]}{int(d[2:10]):08d}"
    dv = digito_verificador_cuit(base)
    if dv is not None:
        nuevo = f"{base[:2]}-{base[2:]}-{dv}"
        return nuevo if cuit_es_valido(nuevo) else None
    return cuit_valido_para(d[:2], int(d[2:10]))


def main():
    cuantos = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    print("CUIT válidos generados (personas físicas):\n")
    for i in range(cuantos):
        cuit = cuit_valido_para("20", 20_000_000 + i * 111)
        if cuit:
            print(f"  {cuit}")
    print("\nCUIT válidos generados (personas jurídicas):\n")
    for i in range(cuantos):
        cuit = cuit_valido_para("30", 30_000_000 + i * 111)
        if cuit:
            print(f"  {cuit}")

    print("\nCorrección de los CUITs que ya están cargados:\n")
    for c in ("20-26473674-2", "30-71234567-8"):
        print(f"  {c} -> {corregir(c)}")


if __name__ == "__main__":
    main()