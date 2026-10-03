"""Revisa los CUITs que hay en la base y avisa cuáles no son válidos.

Un CUIT válido tiene 11 dígitos, prefijo correcto (20/23/24/27/30/33/34) y su
último dígito es el **verificador** (módulo 11, norma ARCA). Si el verificador
no cierra, el número no existe: casi siempre es un CUIT tipeado al revés.

Uso:
    python -X utf8 verificar_cuits.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.database import engine
from app.schemas.persona import cuit_es_valido, digito_verificador_cuit


def _sin_guiones(v):
    return "".join(c for c in v if c.isdigit())


def main():
    with engine.connect() as conn:
        filas = conn.execute(text("""
            SELECT p.id, p.nombre, p.apellido, p.cuit,
                   (c.id IS NOT NULL) AS es_cliente,
                   (pv.id IS NOT NULL) AS es_proveedor
            FROM personas p
            LEFT JOIN clientes c ON c.persona_id = p.id
            LEFT JOIN proveedores pv ON pv.persona_id = p.id
            WHERE COALESCE(p.cuit, '') <> ''
            ORDER BY p.id
        """)).all()

    if not filas:
        print("No hay CUITs cargados.")
        return

    malos = []
    print("CUIT cargado en la base:\n")
    for pid, nombre, apellido, cuit, es_cli, es_prov in filas:
        donde = []
        if es_cli:
            donde.append("cliente")
        if es_prov:
            donde.append("proveedor")
        etiqueta = f"{nombre} {apellido or ''}".strip()
        if cuit_es_valido(cuit):
            print(f"  OK    {cuit:<16} {etiqueta} ({', '.join(donde)})")
        else:
            d = _sin_guiones(cuit)
            esperado = digito_verificador_cuit(d[:10]) if len(d) == 11 else None
            detalle = (
                f"le corresponde terminar en {esperado}"
                if esperado is not None
                else "no es posible (el resto da 1)"
            )
            print(f"  FALLA {cuit:<16} {etiqueta} ({', '.join(donde)}) -> {detalle}")
            malos.append((cuit, etiqueta, esperado))

    if not malos:
        print("\nTodos los CUITs cargados son válidos.")
        return

    print(f"\n{'=' * 70}")
    print(f"{len(malos)} CUIT(s) NO válidos:\n")
    for cuit, etiqueta, esperado in malos:
        correcto = f"{_sin_guiones(cuit)[:10]}-{esperado}"
        print(f"  {etiqueta}")
        print(f"    está:  {cuit}")
        print(f"    sería: {correcto}")
    print(
        "\nOjo: estos números pueden estar mal porque el cliente se equivocó al"
        "\ndarlo de alta, o porque sean CUITs inventados de prueba. No se cambia"
        "\nnada solo: revisá con el cliente cuál es el verdadero."
    )


if __name__ == "__main__":
    main()