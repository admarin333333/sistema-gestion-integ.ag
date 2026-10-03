import sys

sys.path.insert(0, r"C:\proyecto-gestion-contable\backend")
from sqlalchemy import text
from app.database import engine

with engine.connect() as conn:
    cols = [r[0] for r in conn.execute(text("SHOW COLUMNS FROM facturas"))]
    print("columnas de facturas:", ", ".join(cols))
    dinero = next((c for c in ("importe_total", "total", "importe", "monto") if c in cols), None)

    print("\n=== FACTURAS HUERFANAS ===")
    sel = f"SELECT f.id, f.numero, f.fecha, f.{dinero}, f.cliente_id" if dinero else "SELECT f.id, f.numero, f.fecha, f.cliente_id"
    for r in conn.execute(text(sel + " FROM facturas f WHERE f.cliente_id NOT IN (SELECT id FROM clientes) ORDER BY f.id")):
        print("  ", r)

    print("\n=== FACTURAS CON CLIENTE OK ===")
    sel2 = f"SELECT f.id, f.numero, f.{dinero}, f.cliente_id, p.nombre, p.apellido" if dinero else "SELECT f.id, f.numero, f.cliente_id, p.nombre, p.apellido"
    for r in conn.execute(text(sel2 + """
        FROM facturas f JOIN clientes c ON c.id = f.cliente_id
        JOIN personas p ON p.id = c.persona_id ORDER BY f.id
    """)):
        print("  ", r)

    print("\n=== HUERFANAS EN OTRAS TABLAS ===")
    for tabla, col in (("recibos", "cliente_id"), ("anticipos", "cliente_id"),
                       ("cliente_servicio", "cliente_id"), ("bal_rt54_ejercicios", "cliente_id"),
                       ("sugerencias", "cliente_id"), ("compras", "proveedor_id")):
        h = conn.execute(text(
            f"SELECT COUNT(*) FROM {tabla} WHERE {col} IS NOT NULL AND {col} NOT IN (SELECT id FROM {col.split('_')[0]}s)"
        )).scalar()
        total = conn.execute(text(f"SELECT COUNT(*) FROM {tabla}")).scalar()
        print(f"  {tabla}: {h} huerfanas de {total} filas")