"""AVISO: este script MODIFICA el ESQUEMA de la base a la que apunte.

    NO lo corras sin leer esto.

Qué hacía: agregar la columna `presenta_eecc` a la tabla `clientes`. Primero la
creaba con el nombre mal escrito (`presents_eecc`, error de traducción) y después
la renombraba.

Contra qué base: `app.database` lee `DB_NAME` del entorno. Sin esa variable, usa
`gestion_contable` — la del estudio.

POR QUÉ ESTÁ ACA Y NO CORRE

La columna ya está en el modelo (`app/models/`), así que Alembic la crea. Y este
script ya no funcionaría: `create_all` no agrega columnas a una tabla que ya
existe, así que el `ALTER` es redundante y el `RENAME` fallaría con "Unknown
column".

Si alguna vez hay que agregarla a una base vieja, el camino es Alembic:

    alembic revision --autogenerate -m "presenta_eecc en clientes"
    alembic upgrade head

NUNCA a mano, y no con este script.

Está acá solo como histórico. Se puede borrar sin consecuencia: Git conserva el
historial.
"""

import os
import sys

import sqlalchemy as sa  # noqa: F401
from sqlalchemy import text

sys.path.insert(0, r'C:\proyecto-gestion-contable\backend')
os.chdir(r'C:\proyecto-gestion-contable\backend')
from app.database import Base, engine  # noqa: E402,F401

print("Base a la que se conecta:", engine.url.database)
print("AVISO: esta base ya tiene la columna; no hace falta correr nada.")
print("Para agregar columnas nuevas, usá Alembic (ver el docstring).")

# Verificar
from sqlalchemy import inspect  # noqa: E402

insp = inspect(engine)
cols = {c['name'] for c in insp.get_columns('clientes')}
print('presenta_eecc en la base:', 'presenta_eecc' in cols)
