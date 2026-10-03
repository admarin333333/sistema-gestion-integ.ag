"""Crea la tabla `propietario` (datos del estudio + hasta 4 correos)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.database import engine

SQL = """
CREATE TABLE IF NOT EXISTS propietario (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(120) NOT NULL DEFAULT '',
    cuit VARCHAR(13) NULL,
    actividad VARCHAR(120) NULL,
    calle VARCHAR(30) NULL,
    numero_calle VARCHAR(10) NULL,
    localidad VARCHAR(100) NULL,
    provincia VARCHAR(100) NULL,
    codigo_postal VARCHAR(4) NULL,
    telefono VARCHAR(20) NULL,
    cod_area VARCHAR(5) NULL,
    email_1 VARCHAR(120) NULL,
    email_2 VARCHAR(120) NULL,
    email_3 VARCHAR(120) NULL,
    email_4 VARCHAR(120) NULL,
    aviso_vencimientos TINYINT(1) NOT NULL DEFAULT 1,
    observaciones TEXT NULL,
    fecha_alta DATE NOT NULL,
    creado DATETIME NOT NULL,
    actualizado DATETIME NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""


def main():
    with engine.begin() as conn:
        conn.execute(text(SQL))
        print("Tabla propietario lista")
        # Una fila vacía para que la pantalla la muestre de entrada.
        hay = conn.execute(text("SELECT COUNT(*) FROM propietario")).scalar()
        if hay == 0:
            conn.execute(
                text(
                    "INSERT INTO propietario (nombre, fecha_alta, creado) "
                    "VALUES ('', CURDATE(), NOW())"
                )
            )
            print("Fila inicial creada")


if __name__ == "__main__":
    main()