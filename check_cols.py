import sys
import os
sys.path.insert(0, r'C:\proyecto-gestion-contable\backend')
os.chdir(r'C:\proyecto-gestion-contable\backend')
from app.database import Base, engine
from sqlalchemy import inspect
insp = inspect(engine)
print('Columnas clientes:', insp.get_columns('clientes'))