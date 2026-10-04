"""
Agrega a `bal_rt54_ejercicios` los campos del ejercicio contable:

- `anio_inicio` / `anio_fin`: el año que elige el usuario (solo el año).
- `dia_mes_cierre`: día y mes de cierre que se copia del cliente al crear el
  balance (el día siguiente al cierre es el inicio del ejercicio siguiente).

Con esos tres datos el backend arma el intervalo:
  ejercicio_inicio = (anio_inicio + 1) al día/mes de cierre - 1 día
  ejercicio_fin    = (anio_fin + 1) al día/mes de cierre - 1 día
Ej.: cierre 31/07, anio_inicio 2024, anio_fin 2025
  → 01/08/2024 a 31/07/2025
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import engine

NUEVOS = (
    ("anio_inicio", "SMALLINT NULL"),
    ("anio_fin", "SMALLINT NULL"),
    ("dia_mes_cierre", "TINYINT NULL"),   # 1..31
    ("mes_cierre", "TINYINT NULL"),      # 1..12
)


def main():
    with engine.begin() as conn:
        existentes = {r[0] for r in conn.execute(text("SHOW COLUMNS FROM bal_rt54_ejercicios"))}
        for nombre, tipo in NUEVOS:
            if nombre not in existentes:
                conn.execute(text(f"ALTER TABLE bal_rt54_ejercicios ADD COLUMN {nombre} {tipo}"))
                print(f"  + {nombre} {tipo}")
            else:
                print(f"  = {nombre} ya existe")

        # Rellena con lo que ya hay para no dejar filas incompletas.
        conn.execute(text("""
            UPDATE bal_rt54_ejercicios
            SET anio_inicio = YEAR(fecha_inicio),
                anio_fin    = YEAR(fecha_fin),
                dia_mes_cierre = DAY(fecha_fin),
                mes_cierre     = MONTH(fecha_fin)
            WHERE anio_inicio IS NULL
        """))
        print("Datos existentes rellenados")

        for r in conn.execute(text("""
            SELECT id, nombre, fecha_inicio, fecha_fin, anio_inicio, anio_fin,
                   dia_mes_cierre, mes_cierre
            FROM bal_rt54_ejercicios ORDER BY id
        """)):
            print(f"  balance {r[0]} '{r[1]}': {r[2]} → {r[3]} "
                  f"(años {r[4]}-{r[5]}, cierre día {r[6]} mes {r[7]})")

    print("\nMigración del balance terminada")


if __name__ == "__main__":
    main()