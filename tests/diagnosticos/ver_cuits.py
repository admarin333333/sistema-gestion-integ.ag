import sys

sys.path.insert(0, r"C:\proyecto-gestion-contable\backend")
from sqlalchemy import text
from app.database import engine

with engine.connect() as conn:
    print("=== CLIENTES ===")
    for r in conn.execute(text("""
        SELECT c.nro_cuenta, p.nombre, p.apellido, p.cuit
        FROM clientes c JOIN personas p ON p.id = c.persona_id
        ORDER BY c.nro_cuenta
    """)):
        cuit = r[3] or ""
        dig = cuit[-1] if cuit else "?"
        print(f"  cuenta {r[0]}: {r[1]} {r[2] or ''} | cuit {cuit or '(sin cuit)'} | ultimo digito {dig}")

    print("\n=== PROVEEDORES ===")
    for r in conn.execute(text("""
        SELECT pr.nro_cuenta, p.nombre, p.cuit
        FROM proveedores pr JOIN personas p ON p.id = pr.persona_id
        ORDER BY pr.nro_cuenta
    """)):
        print(f"  cuenta {r[0]}: {r[1]} | cuit {r[2] or '(sin cuit)'}")