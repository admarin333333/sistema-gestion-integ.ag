import sqlalchemy as sa
from sqlalchemy import text
import sys
sys.path.insert(0, r'C:\proyecto-gestion-contable\backend')
os = __import__('os')
os.chdir(r'C:\proyecto-gestion-contable\backend')
from app.database import Base, engine

# Agregar columna apresenta_eecc a la tabla clientes
with engine.begin() as conn:
    conn.execute(text("ALTER TABLE clientes ADD COLUMN presents_eecc BOOLEAN NOT NULL DEFAULT TRUE"))
    # Nota: el nombre en la BD fue 'presents_eecc' por un error de traducción;
    # lo corregimos a 'presenta_eecc' agregando otra columna y borrando la antigua.
    # Pero como ya se agregó, renombramos:
    try:
        conn.execute(text("ALTER TABLE clientes RENAME COLUMN presents_eecc TO apresenta_eecc"))
        print("Columna adicionada y renombrada successfully.")
    except Exception as e:
        print("Column already has correct name or error:", e)

# Verificar
from sqlalchemy import inspect
insp = inspect(engine)
cols = {c['name'] for c in insp.get_columns('clientes')}
print('presenta_eecc en BD:', 'presenta_eecc' in cols)