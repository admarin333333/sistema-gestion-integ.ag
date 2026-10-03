"""
Agrega la **clave fiscal de ARCA** a las personas (clientes y proveedores).

Motivo: la clave fiscal es lo que permite trabajar en ARCA en nombre del
contribuyente. Va junto al CUIT (misma tabla `personas`) porque es un dato
del contribuyente, no del módulo en el que está cargado.

Agrega tres columnas a `personas`:
- `clave_fiscal`: la clave de ARCA (11 caracteres alfanuméricos).
- `fecha_carga_clave_fiscal`: cuándo se cargó **por primera vez**.
- `fecha_modif_clave_fiscal`: cuándo se cambió por **última vez**.

Y crea la tabla `clave_fiscal_historial`: **una fila cada vez que la clave
cambia** (no una fila por persona). Guarda la clave anterior, la nueva, la
fecha y quién lo hizo, para saber con qué clave se presentó cada cosa.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import engine

COLUMNAS = (
    ("clave_fiscal", "VARCHAR(11) NULL"),
    ("fecha_carga_clave_fiscal", "DATE NULL"),
    ("fecha_modif_clave_fiscal", "DATETIME NULL"),
)

CREATE_HISTORIAL = """
CREATE TABLE IF NOT EXISTS clave_fiscal_historial (
    id INT AUTO_INCREMENT PRIMARY KEY,
    persona_id INT NOT NULL,
    clave_fiscal_anterior VARCHAR(11) NULL,
    clave_fiscal_nueva VARCHAR(11) NULL,
    fecha_cambio DATETIME NOT NULL,
    usuario VARCHAR(60) NULL,
    CONSTRAINT fk_clave_fiscal_historial_persona
        FOREIGN KEY (persona_id) REFERENCES personas(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""


def main():
    with engine.begin() as conn:
        existentes = {r[0] for r in conn.execute(text("SHOW COLUMNS FROM personas"))}
        for nombre, tipo in COLUMNAS:
            if nombre not in existentes:
                conn.execute(text(f"ALTER TABLE personas ADD COLUMN {nombre} {tipo}"))
                print(f"  + personas.{nombre} {tipo}")
            else:
                print(f"  = personas.{nombre} ya existe")

        conn.execute(text(CREATE_HISTORIAL))
        print("  = clave_fiscal_historial lista")

        # Índice para buscar el historial de una persona rápido.
        conn.execute(text(
            "CREATE INDEX ix_clave_fiscal_historial_persona "
            "ON clave_fiscal_historial (persona_id)"
        ))
        print("  + índice por persona")

        print("\nPersonas con clave fiscal:")
        filas = conn.execute(text("""
            SELECT id, nombre, apellido, cuit, clave_fiscal,
                   fecha_carga_clave_fiscal, fecha_modif_clave_fiscal
            FROM personas
            WHERE clave_fiscal IS NOT NULL
            ORDER BY id
        """)).all()
        if not filas:
            print("  (ninguna todavía)")
        for r in filas:
            nombre = f"{r[2]}, {r[1]}" if r[2] else r[1]
            print(f"  #{r[0]} {nombre} ({r[3]}) clave={r[4]} "
                  f"carga={r[5]} última modif={r[6]}")

    print("\nMigración de clave fiscal terminada")


if __name__ == "__main__":
    main()