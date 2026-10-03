import sys
sys.path.insert(0, r"C:\proyecto-gestion-contable\backend")
from sqlalchemy import text
from app.database import engine

with engine.begin() as conn:
    r = conn.execute(text("SELECT email FROM personas WHERE nombre = :n"), {"n": "PROVEEDOR"}).scalar()
    print("email guardado:", r)
    conn.execute(text("UPDATE personas SET email = NULL WHERE nombre = :n"), {"n": "PROVEEDOR"})
    print("limpiado a null")