"""
Convierte el catálogo de vencimientos en una tabla editable.

Antes los conceptos estaban fijos en el código (`IMPUESTOS` en
`models/vencimiento_impositivo.py`), así que agregar uno era cambiar Python.
Ahora viven en `conceptos_vencimiento` y se dan de alta desde Configuración
(por ejemplo "Libro IVA Digital", que no es un impuesto).

Crea la tabla y la llena con los 8 conceptos de fábrica + **DDJJ F.931**.
Es idempotente: si se corre dos veces no rompe nada.

Uso:  python -X utf8 migrar_conceptos_vencimiento.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.database import engine

CREATE_TABLA = """
CREATE TABLE IF NOT EXISTS conceptos_vencimiento (
    id INT AUTO_INCREMENT PRIMARY KEY,
    clave VARCHAR(40) NOT NULL,
    nombre VARCHAR(80) NOT NULL,
    orden TINYINT NOT NULL DEFAULT 0,
    sistema TINYINT(1) NOT NULL DEFAULT 0,
    activo TINYINT(1) NOT NULL DEFAULT 1,
    creado DATETIME NOT NULL,
    actualizado DATETIME NULL,
    CONSTRAINT uq_conceptos_vencimiento_clave UNIQUE (clave)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

# Los que trae el sistema de fábrica. `sistema = 1` significa que no se
# borran (se pueden desactivar), pero se les puede cambiar el nombre.
DE_FABRICA = (
    ("ddjj_iva", "DDJJ IVA"),
    ("sicore_cta", "SICORE - Pago a cuenta"),
    ("ddjj_sicore", "DDJJ SICORE"),
    ("ddjj_ganancias", "DDJJ Impuesto a las Ganancias"),
    ("monotributo", "Monotributo"),
    ("ddjj_f931", "DDJJ F.931"),
    ("convenio_multilateral", "Convenio multilateral"),
    ("anticipo_fondo_coop", "Anticipo Fondo Cooperativo"),
    ("ddjj_fondo_coop", "DDJJ Fondo Cooperativo"),
)


def main():
    with engine.begin() as conn:
        conn.execute(text(CREATE_TABLA))
        print("Tabla conceptos_vencimiento lista")

        for orden, (clave, nombre) in enumerate(DE_FABRICA, start=1):
            existe = conn.execute(
                text("SELECT id FROM conceptos_vencimiento WHERE clave = :c"),
                {"c": clave},
            ).first()
            if existe:
                # Solo actualiza el nombre si sigue siendo el de fábrica.
                conn.execute(
                    text(
                        "UPDATE conceptos_vencimiento SET nombre = :n, orden = :o "
                        "WHERE clave = :c AND sistema = 1"
                    ),
                    {"n": nombre, "o": orden, "c": clave},
                )
                print(f"  = {clave} ya existe")
            else:
                conn.execute(
                    text(
                        "INSERT INTO conceptos_vencimiento "
                        "(clave, nombre, orden, sistema, activo, creado) "
                        "VALUES (:c, :n, :o, 1, 1, NOW())"
                    ),
                    {"c": clave, "n": nombre, "o": orden},
                )
                print(f"  + {clave:<24} {nombre}")

    with engine.connect() as conn:
        print("\nCatálogo de conceptos:")
        for r in conn.execute(
            text(
                "SELECT clave, nombre, orden, activo FROM conceptos_vencimiento "
                "ORDER BY orden, nombre"
            )
        ):
            marca = "" if r[3] else "  (inactivo)"
            print(f"  {r[2]:>2}. {r[0]:<24} {r[1]}{marca}")

    print("\nMigración de conceptos terminada")


if __name__ == "__main__":
    main()