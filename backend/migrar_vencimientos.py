"""Crea la tabla `vencimientos_impositivos` (mes/año + dígito + impuesto + fecha)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.database import engine

SQL = """
CREATE TABLE IF NOT EXISTS vencimientos_impositivos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    anio SMALLINT NOT NULL,
    mes SMALLINT NOT NULL,
    ultimo_digito SMALLINT NOT NULL,
    impuesto VARCHAR(40) NOT NULL,
    fecha_vencimiento DATE NOT NULL,
    creado DATETIME NOT NULL,
    actualizado DATETIME NULL,
    UNIQUE KEY uq_venc_periodo_digito_impuesto (anio, mes, ultimo_digito, impuesto),
    INDEX ix_venc_periodo (anio, mes),
    INDEX ix_venc_digito (ultimo_digito)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""


def main():
    with engine.begin() as conn:
        conn.execute(text(SQL))
        print("Tabla vencimientos_impositivos lista")
        total = conn.execute(text("SELECT COUNT(*) FROM vencimientos_impositivos")).scalar()
        print(f"Filas: {total}")


if __name__ == "__main__":
    main()