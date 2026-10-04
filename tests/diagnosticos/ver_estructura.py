import sys
sys.path.insert(0, r'C:\proyecto-gestion-contable\backend')
from sqlalchemy import text
from app.database import engine

with engine.connect() as conn:
    # Ver estructura de clientes_vieja
    result = conn.execute(text("SHOW CREATE TABLE clientes_vieja"))
    print("=== CLIENTES_VIEJA ===")
    print(result.fetchone()[1])
    
    # Ver estructura de clientes (nueva)
    result = conn.execute(text("SHOW CREATE TABLE clientes"))
    print("\n=== CLIENTES (NUEVA) ===")
    print(result.fetchone()[1])
    
    # Ver datos de clientes_vieja
    result = conn.execute(text("SELECT id, nro_cuenta, tipo, nombre FROM clientes_vieja"))
    print("\n=== DATOS CLIENTES_VIEJA ===")
    for row in result:
        print(f"  id={row[0]}, nro_cuenta={row[1]}, tipo={row[2]}, nombre={row[3]}")
    
    # Ver datos de clientes (nueva)
    result = conn.execute(text("SELECT id, persona_id, nro_cuenta FROM clientes"))
    print("\n=== DATOS CLIENTES (NUEVA) ===")
    for row in result:
        print(f"  id={row[0]}, persona_id={row[1]}, nro_cuenta={row[2]}")