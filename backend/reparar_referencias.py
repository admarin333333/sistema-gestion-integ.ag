"""
Repara lo que quedó colgando de la migración de personas:

1. Filas que guardan el id VIEJO del cliente (22, 121) en vez del nuevo.
2. Vuelve a poner las claves foráneas que se perdieron al recrear las tablas.

Id viejo -> cliente nuevo:
  22  (sandra)  -> 12
  121 (SOLEDAD) -> 14
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.database import engine

# id viejo -> id nuevo (sacados de personas/clientes)
MAPA = {22: 12, 121: 14}


def main():
    with engine.begin() as conn:
        print("--- 1. Corrigiendo filas con id de cliente viejo ---")
        for tabla in ("facturas", "recibos", "anticipos", "sugerencias",
                      "cliente_servicio", "bal_rt54_ejercicios"):
            existentes = {r[0] for r in conn.execute(text(f"SHOW TABLES LIKE '{tabla}'"))}
            if not existentes:
                continue
            for viejo, nuevo in MAPA.items():
                n = conn.execute(
                    text(f"UPDATE {tabla} SET cliente_id = :nuevo WHERE cliente_id = :viejo"),
                    {"viejo": viejo, "nuevo": nuevo},
                ).rowcount
                if n:
                    print(f"  {tabla}: {n} fila(s) {viejo} -> {nuevo}")

        print("\n--- 2. Reponiendo claves foraneas ---")
        # (tabla, columna, tabla referenciada, nombre de la restriccion)
        FKS = (
            ("facturas", "cliente_id", "clientes", "fk_facturas_cliente"),
            ("recibos", "cliente_id", "clientes", "fk_recibos_cliente"),
            ("anticipos", "cliente_id", "clientes", "fk_anticipos_cliente"),
            ("sugerencias", "cliente_id", "clientes", "fk_sugerencias_cliente"),
            ("cliente_servicio", "cliente_id", "clientes", "fk_cs_cliente"),
            ("bal_rt54_ejercicios", "cliente_id", "clientes", "fk_bal_cliente"),
            ("compras", "proveedor_id", "proveedores", "fk_compras_proveedor"),
        )
        for tabla, col, ref, nombre in FKS:
            ya_esta = conn.execute(
                text("""
                    SELECT COUNT(*) FROM information_schema.KEY_COLUMN_USAGE
                    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t
                      AND COLUMN_NAME = :c AND REFERENCED_TABLE_NAME = :r
                """),
                {"t": tabla, "c": col, "r": ref},
            ).scalar()
            if ya_esta:
                print(f"  = {tabla}.{col} ya tiene FK a {ref}")
                continue
            try:
                conn.execute(text(
                    f"ALTER TABLE {tabla} ADD CONSTRAINT {nombre} "
                    f"FOREIGN KEY ({col}) REFERENCES {ref}(id)"
                ))
                print(f"  + {tabla}.{col} -> {ref}")
            except Exception as ex:
                print(f"  ! {tabla}.{col}: {str(ex)[:90]}")

    print("\n--- 3. Verificacion final ---")
    with engine.connect() as conn:
        for tabla, col in (("facturas", "cliente_id"), ("recibos", "cliente_id"),
                           ("anticipos", "cliente_id"), ("cliente_servicio", "cliente_id"),
                           ("bal_rt54_ejercicios", "cliente_id"), ("sugerencias", "cliente_id")):
            h = conn.execute(text(
                f"SELECT COUNT(*) FROM {tabla} WHERE {col} IS NOT NULL "
                f"AND {col} NOT IN (SELECT id FROM clientes)"
            )).scalar()
            total = conn.execute(text(f"SELECT COUNT(*) FROM {tabla}")).scalar()
            marca = "OK" if h == 0 else "HUEFANAS"
            print(f"  {marca}: {tabla} {h} de {total}")
        h = conn.execute(text(
            "SELECT COUNT(*) FROM compras WHERE proveedor_id NOT IN (SELECT id FROM proveedores)"
        )).scalar()
        print(f"  {'OK' if h == 0 else 'HUEFANAS'}: compras {h}")


if __name__ == "__main__":
    main()