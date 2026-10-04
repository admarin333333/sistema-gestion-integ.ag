"""
AVISO: NO CORRAS ESTE SCRIPT. Borrar datos de un cliente real es posible.

Está acá solo como histórico. Ver `LEEME.md` de esta carpeta.

POR QUÉ NO SE DEBE CORRER

Dos motivos, ambos sobre datos tuyos:

1. **El CUIT de abajo está mal escrito.** El script borra parte del historial de
   clave fiscal del CUIT `20-26473674-2`. El CUIT real del cliente Juan Pérez es
   `20-26473675-8` — se diferencian en el último dígito (2 contra 8).

   Hoy no borra nada, porque no hay ninguna persona con ese CUIT. Pero si algún
   día alguien "corrige" el dígito para que coincida, el script pasa a borrar
   datos de un cliente real. Es el peor tipo de bug: invisible hasta que hace
   daño.

2. **El filtro de nombres incluye `'Distribuidora Norte SRL'`,** que es un
   cliente real tuyo (id 11). Hoy no lo toca porque tiene CUIT cargado, así que
   no entra en el criterio de "sin CUIT y sin DNI". Pero si esa persona queda
   alguna vez sin CUIT, el script la borra sin preguntar.

Lo que sí es cierto: solo borra clientes SIN movimientos asociados (facturas,
recibos, anticipos, compras). Eso protege a los que tienen historia, pero no a
los que no la tienen — que es justamente el caso de los clientes que uno no
quiere perder sin darse cuenta.

Si alguna vez hay que borrar duplicados de prueba, usar
`backend/limpiar_clientes_prueba.py`, que busca por una lista de CUITs y DNI
concretos de los tests, respalda antes y no toca a nadie más.

Uso original:  python -X utf8 limpiar_duplicados_prueba.py
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