"""
Limpia los clientes duplicados que dejaron las corridas de prueba anteriores
(a la que se rompió antes de arreglar las suites).

Son personas físicas/jurídicas de prueba creadas por `test_fase2a` que no
tenían ni CUIT ni DNI, así que no se podían borrar desde la API (ahora el
backend valida que existan los datos y devuelve 422). Solo borra los que
NO tienen movimientos asociados.

Uso:  python -X utf8 limpiar_duplicados_prueba.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.database import engine

# Movimientos que—atcan al cliente (si tiene alguno, NO se toca).
MOVIMIENTOS = (
    ("facturas", "cliente_id"),
    ("recibos", "cliente_id"),
    ("anticipos", "cliente_id"),
    ("compras", "proveedor_id"),
)


def tiene_movimientos(conn, cliente_id: int) -> bool:
    for tabla, columna in MOVIMIENTOS:
        n = conn.execute(
            text(f"SELECT COUNT(*) FROM {tabla} WHERE {columna} = :id"),
            {"id": cliente_id},
        ).scalar()
        if n:
            return True
    return False


def main():
    with engine.begin() as conn:
        # Duplicados de prueba: mismo nombre, sin CUIT y sin DNI.
        candidatos = conn.execute(text("""
            SELECT c.id, p.id, p.nombre, p.apellido, p.cuit, p.dni
            FROM clientes c
            JOIN personas p ON p.id = c.persona_id
            WHERE COALESCE(p.cuit, '') = '' AND COALESCE(p.dni, '') = ''
              AND p.nombre IN ('Distribuidora Norte SRL', 'Prueba', 'Test')
        """)).all()
        if not candidatos:
            print("No hay duplicados de prueba.")
            return

        print(f"Encontrados {len(candidatos)} posibles duplicados:\n")
        borrados = saltados = 0
        for cid, pid, nombre, apellido, cuit, dni in candidatos:
            if tiene_movimientos(conn, cid):
                print(f"  - id {cid} {nombre!r}: tiene movimientos, NO se borra")
                saltados += 1
                continue
            conn.execute(
                text("DELETE FROM sugerencias WHERE cliente_id = :id"), {"id": cid}
            )
            conn.execute(
                text("DELETE FROM cliente_servicio WHERE cliente_id = :id"), {"id": cid}
            )
            conn.execute(text("DELETE FROM clientes WHERE id = :id"), {"id": cid})
            conn.execute(text("DELETE FROM personas WHERE id = :id"), {"id": pid})
            print(f"  - id {cid} {nombre!r} {apellido or ''}: borrado")
            borrados += 1

        # El historial de la clave fiscal de Juan quedó con datos de prueba
        # (PRUEBA123AR etc. los cargué a mano desde el navegador).
        h = conn.execute(text("""
            DELETE h FROM clave_fiscal_historial h
            JOIN personas p ON p.id = h.persona_id
            WHERE p.cuit = '20-26473674-2'
              AND (h.clave_fiscal_anterior LIKE 'PRUEBA%'
                OR h.clave_fiscal_nueva LIKE 'PRUEBA%'
                OR h.clave_fiscal_anterior LIKE 'SEGUNDA%'
                OR h.clave_fiscal_nueva LIKE 'SEGUNDA%')
        """)).rowcount
        if h:
            print(f"\nHistorial de clave fiscal de prueba borrado: {h} filas")

        print(f"\nBorrados: {borrados} · salteados (con movimientos): {saltados}")


if __name__ == "__main__":
    main()