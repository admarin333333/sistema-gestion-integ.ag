import sys
sys.path.insert(0, r'C:\proyecto-gestion-contable\backend')
from sqlalchemy import text
from app.database import engine

with engine.connect() as conn:
    for tabla in ("personas", "clientes", "proveedores"):
        result = conn.execute(text(f"SELECT COUNT(*) FROM {tabla}"))
        count = result.scalar()
        print(f"{tabla}: {count} registros")
    
    print("\n=== Estructura final ===")
    for tabla in ("personas", "clientes", "proveedores"):
        result = conn.execute(text(f"SHOW CREATE TABLE {tabla}"))
        print(f"\n{tabla}:")
        print(result.fetchone()[1])