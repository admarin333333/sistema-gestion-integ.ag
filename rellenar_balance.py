import os
import sys

sys.path.insert(0, r"C:\proyecto-gestion-contable\backend")
from sqlalchemy import text
from app.database import engine

with engine.begin() as conn:
    conn.execute(text("""
        UPDATE bal_rt54_ejercicios
        SET anio_inicio = YEAR(fecha_inicio),
            anio_fin    = YEAR(fecha_fin),
            dia_mes_cierre = DAY(fecha_fin),
            mes_cierre     = MONTH(fecha_fin)
        WHERE anio_inicio IS NULL
    """))
    print("rellenado OK")

with engine.connect() as conn:
    for r in conn.execute(text("""
        SELECT id, nombre, fecha_inicio, fecha_fin, anio_inicio, anio_fin,
               dia_mes_cierre, mes_cierre
        FROM bal_rt54_ejercicios ORDER BY id
    """)):
        print(f"balance {r[0]} '{r[1]}': {r[2]} a {r[3]} | anios {r[4]}-{r[5]} | cierre dia {r[6]} mes {r[7]}")