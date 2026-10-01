import sys
sys.path.insert(0, r'C:\proyecto-gestion-contable\backend')
from app.database import get_db
from sqlalchemy import text

db = next(get_db())
try:
    db.execute(text("ALTER TABLE recibos ADD COLUMN estado VARCHAR(20) NOT NULL DEFAULT 'emitido'"))
    db.commit()
    print('Columna estado agregada')
except Exception as e:
    print('Error:', e)
    db.rollback()