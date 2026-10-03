"""
Agrega `vencimientos_meses`: un registro por cada mes/año guardado.

Sirve para tres cosas a la vez:
1. Saber **cuándo se guardó** cada mes (para el árbol de Configuración).
2. Guardar un **respaldo** del último guardado de ese mes: si más adelante
   borraste algo por error, se puede recuperar desde ahí.
3. Que el sistema **sepa qué meses existen** aunque después los vacíes.

Uso:  python -X utf8 migrar_vencimientos_meses.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.database import engine

SQL = """
CREATE TABLE IF NOT EXISTS vencimientos_meses (
    id INT AUTO_INCREMENT PRIMARY KEY,
    anio SMALLINT NOT NULL,
    mes SMALLINT NOT NULL,
    cantidad INT NOT NULL DEFAULT 0,
    ultimo_cambio DATETIME NOT NULL,
    usuario VARCHAR(60) NULL,
    respaldo LONGTEXT NULL,
    CONSTRAINT uq_vencimientos_meses UNIQUE (anio, mes)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""


def main():
    with engine.begin() as conn:
        conn.execute(text(SQL))
        print("Tabla vencimientos_meses lista")

        # Rellena con los meses que ya estaban cargados, para no perder el
        # historial de lo que hay hoy.
        rows = conn.execute(text("""
            SELECT anio, mes, COUNT(*) AS cantidad, MAX(creado) AS ultimo
            FROM vencimientos_impositivos
            GROUP BY anio, mes
        """)).all()
        for anio, mes, cantidad, ultimo in rows:
            conn.execute(
                text(
                    "INSERT INTO vencimientos_meses (anio, mes, cantidad, ultimo_cambio) "
                    "VALUES (:a, :m, :c, :u) "
                    "ON DUPLICATE KEY UPDATE cantidad = VALUES(cantidad), "
                    "ultimo_cambio = VALUES(ultimo_cambio)"
                ),
                {"a": anio, "m": mes, "c": cantidad, "u": ultimo},
            )
            print(f"  = {anio}-{mes:02d}: {cantidad} vencimientos")

        # Respaldo inicial de cada mes (por si hay que recuperar).
        for anio, mes in conn.execute(
            text("SELECT anio, mes FROM vencimientos_meses")
        ).all():
            filas = conn.execute(
                text(
                    "SELECT ultimo_digito, impuesto, fecha_vencimiento "
                    "FROM vencimientos_impositivos "
                    "WHERE anio = :a AND mes = :m "
                    "ORDER BY ultimo_digito, impuesto"
                ),
                {"a": anio, "m": mes},
            ).all()
            import json

            conn.execute(
                text(
                    "UPDATE vencimientos_meses SET respaldo = :r "
                    "WHERE anio = :a AND mes = :m"
                ),
                {
                    "r": json.dumps(
                        [
                            {
                                "ultimo_digito": f[0],
                                "impuesto": f[1],
                                "fecha_vencimiento": f[2].isoformat(),
                            }
                            for f in filas
                        ]
                    ),
                    "a": anio,
                    "m": mes,
                },
            )

    print("\nMigración terminada")


if __name__ == "__main__":
    main()