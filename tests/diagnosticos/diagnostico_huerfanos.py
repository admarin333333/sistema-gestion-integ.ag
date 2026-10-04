import sys

sys.path.insert(0, r"C:\proyecto-gestion-contable\backend")
from sqlalchemy import text
from app.database import engine

with engine.connect() as conn:
    print("=== MAPA: persona -> cliente/proveedor ===")
    for r in conn.execute(text("""
        SELECT p.id, p.nombre, p.apellido, c.id, c.nro_cuenta, pr.id, pr.nro_cuenta
        FROM personas p
        LEFT JOIN clientes c ON c.persona_id = p.id
        LEFT JOIN proveedores pr ON pr.persona_id = p.id
        ORDER BY p.id
    """)):
        print(f"  persona {r[0]} {r[1]} {r[2] or ''} -> cliente {r[3]} (cuenta {r[4]}) | proveedor {r[5]} (cuenta {r[6]})")

    print("\n=== FACTURA 85 (huerfana, apunta a cliente_id 22) ===")
    for r in conn.execute(text("""
        SELECT id, numero, concepto, importe, cliente_id, fecha, estado
        FROM facturas WHERE id = 85
    """)):
        print("  ", r)

    print("\n=== cliente_servicio huerfanas ===")
    for r in conn.execute(text("""
        SELECT cs.id, cs.cliente_id, s.nombre
        FROM cliente_servicio cs
        LEFT JOIN servicios s ON s.id = cs.servicio_id
        WHERE cs.cliente_id NOT IN (SELECT id FROM clientes)
    """)):
        print("  ", r)

    print("\n=== TODAS las filas de cliente_servicio ===")
    for r in conn.execute(text("SELECT id, cliente_id, servicio_id FROM cliente_servicio ORDER BY id")):
        print("  ", r)