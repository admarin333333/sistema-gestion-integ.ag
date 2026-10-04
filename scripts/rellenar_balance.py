"""AVISO: este script MODIFICA datos de la base a la que apunte.

    NO lo corras sin leer esto.

Qué hacía: completar los años y la fecha de cierre de los balances RT54 que los
tenían en NULL, derivándolos de `fecha_inicio` y `fecha_fin`.

Contra qué base: `app.database` lee `DB_NAME` del entorno. Sin esa variable, usa
`gestion_contable` — la del estudio.

Si lo corres hoy contra la base real no hace nada: los 2 balances tienen los
datos cargados (verificado: `anio_inicio`, `anio_fin`, `dia_mes_cierre` y
`mes_cierre` ya están). El `WHERE anio_inicio IS NULL` no encuentra a nadie.

Ojo igual con la lógica: el día de cierre se saca del `fecha_fin` del ejercicio.
Si el ejercicio va del 01/08/2024 al 31/07/2025, `fecha_fin` da 31/07, que es el
cierre correcto. Pero si un ejercicio termina el 31/12, el cierre quedaría
31/12, que puede no ser lo que el contador quiso. Para eso está el campo
`fecha_cierre_ejercicio` de la ficha del cliente, que el backend usa cuando crea
un balance nuevo.

Está acá solo como histórico. Se puede borrar sin consecuencia: Git conserva el
historial.
"""

import os
import sys

sys.path.insert(0, r"C:\proyecto-gestion-contable\backend")
from sqlalchemy import text  # noqa: E402

from app.database import engine  # noqa: E402

print("Base a la que se conecta:", engine.url.database)

with engine.connect() as conn:
    pendientes = conn.execute(
        text("SELECT COUNT(*) FROM bal_rt54_ejercicios WHERE anio_inicio IS NULL")
    ).scalar()
    print("balances con los años sin cargar:", pendientes)
    if pendientes:
        print("AVISO: hay balances incompletos. Mirá el docstring antes de seguir.")

# Verificación (solo lectura)
with engine.connect() as conn:
    for r in conn.execute(text("""
        SELECT id, nombre, fecha_inicio, fecha_fin, anio_inicio, anio_fin,
               dia_mes_cierre, mes_cierre
        FROM bal_rt54_ejercicios ORDER BY id
    """)):
        print(f"balance {r[0]} '{r[1]}': {r[2]} a {r[3]} | anios {r[4]}-{r[5]} | cierre dia {r[6]} mes {r[7]}")
