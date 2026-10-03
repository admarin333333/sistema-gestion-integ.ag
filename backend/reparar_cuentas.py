"""
Reparación: completa los números de cuenta de clientes y proveedores.

El problema: el INSERT original usaba un JOIN por (nombre, cuit, dni), pero con
cuit = NULL la comparación `cuit = NULL` nunca es verdadera, así que solo
migró el registro con CUIT. Ahora se hace por posición: se recorre la tabla
personas en orden de id y se asigna el correlativo que le corresponde.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import engine


def main():
    with engine.begin() as conn:
        # Las personas que ya están en alguna tabla no se tocan.
        # Para el resto, se asigna cliente o proveedor según se haya migrado antes.
        ya_asignadas = {
            r[0] for r in conn.execute(text("SELECT persona_id FROM clientes"))
        }

        print(f"Personas ya en clientes: {len(ya_asignadas)}")

        # Última persona de clientes: por id de persona (orden de alta original)
        if ya_asignadas:
            ultimo_id = conn.execute(
                text("SELECT MAX(persona_id) FROM clientes")
            ).scalar()
        else:
            ultimo_id = None

        # Correlativo actual de clientes
        max_cli = conn.execute(text("SELECT MAX(nro_cuenta) FROM clientes")).scalar() or 0
        max_prov = conn.execute(text("SELECT MAX(nro_cuenta) FROM proveedores")).scalar() or 0

        print(f"Correlativos actuales -> clientes: {max_cli}, proveedores: {max_prov}")

        # Personas sin asignar, en orden de id
        pendientes = conn.execute(
            text("""
                SELECT p.id FROM personas p
                LEFT JOIN clientes c ON c.persona_id = p.id
                LEFT JOIN proveedores pr ON pr.persona_id = p.id
                WHERE c.id IS NULL AND pr.id IS NULL
                ORDER BY p.id
            """)
        ).fetchall()

        print(f"Personas pendientes de asignar: {len(pendientes)}")

        for (persona_id,) in pendientes:
            # Criterio: los que tienen dni = '5555555' (PROVEEDOR) y en general
            # los que tenían tipo = 'proveedor' en la tabla vieja.
            # Como la tabla vieja ya no existe, se usa el nombre como criterio:
            # el proveedor de prueba se llama PROVEEDOR.
            es_proveedor = conn.execute(
                text("SELECT nombre FROM personas WHERE id = :i"),
                {"i": persona_id},
            ).scalar() == "PROVEEDOR"

            if es_proveedor:
                max_prov += 1
                conn.execute(
                    text("INSERT INTO proveedores (persona_id, nro_cuenta) VALUES (:p, :n)"),
                    {"p": persona_id, "n": max_prov},
                )
                print(f"  persona {persona_id} -> PROVEEDOR nro_cuenta={max_prov}")
            else:
                max_cli += 1
                conn.execute(
                    text("INSERT INTO clientes (persona_id, nro_cuenta) VALUES (:p, :n)"),
                    {"p": persona_id, "n": max_cli},
                )
                print(f"  persona {persona_id} -> CLIENTE nro_cuenta={max_cli}")

    print("\nReparación terminada")


if __name__ == "__main__":
    main()