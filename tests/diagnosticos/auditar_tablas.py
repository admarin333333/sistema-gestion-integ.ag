import sys

sys.path.insert(0, r"C:\proyecto-gestion-contable\backend")
from sqlalchemy import text
from app.database import engine

with engine.connect() as conn:
    print("=== TODAS LAS CLAVES FORANEAS ===")
    for r in conn.execute(text("""
        SELECT TABLE_NAME, COLUMN_NAME,
               REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = DATABASE() AND REFERENCED_TABLE_NAME IS NOT NULL
        ORDER BY REFERENCED_TABLE_NAME, TABLE_NAME
    """)):
        print(f"  {r[1]:<18} de {r[0]:<22} -> {r[3]} de {r[2]}")

    print("\n=== ¿ALGUNA TABLA CRUZA clientes Y proveedores? ===")
    cruces = []
    for r in conn.execute(text("""
        SELECT TABLE_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = DATABASE() AND REFERENCED_TABLE_NAME IS NOT NULL
        GROUP BY TABLE_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME
        ORDER BY TABLE_NAME
    """)):
        tabla, columna, ref = r
        if tabla in ("clientes", "proveedores"):
            continue
        refs_clientes = set()
        refs_proveedores = set()
        for x in conn.execute(text("""
            SELECT DISTINCT REFERENCED_TABLE_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t AND COLUMN_NAME = :c
              AND REFERENCED_TABLE_NAME IS NOT NULL
        """), {"t": tabla, "c": columna}):
            refs_clientes.add(x[0])
        if "clientes" in refs_clientes:
            cruces.append(f"{tabla}.{columna} -> clientes")
        if "proveedores" in refs_clientes:
            cruces.append(f"{tabla}.{columna} -> proveedores")
    if cruces:
        for c in cruces:
            print("  CRUCE:", c)
    else:
        print("  Ninguna: cada tabla apunta a un solo modulo")

    print("\n=== PERSONAS QUE ESTAN EN LOS DOS MODULOS ===")
    n = conn.execute(text("""
        SELECT COUNT(*) FROM clientes c JOIN proveedores p ON c.persona_id = p.persona_id
    """)).scalar()
    print(f"  {n}")

    print("\n=== INTEGRIDAD: filas huerfanas ===")
    for tabla, col in (("clientes", "persona_id"), ("proveedores", "persona_id"),
                       ("facturas", "cliente_id"), ("compras", "proveedor_id")):
        h = conn.execute(text(
            f"SELECT COUNT(*) FROM {tabla} t LEFT JOIN personas pe ON pe.id = t.{col} "
            f"WHERE t.{col} IS NOT NULL AND pe.id IS NULL"
        )).scalar()
        print(f"  {tabla} sin persona: {h}")

    print("\n=== FKs que apuntan a clientes/proveedores pero con datos cruzados ===")
    # Compras no deberia apuntar a una persona que esta en clientes
    mal = conn.execute(text("""
        SELECT COUNT(*) FROM compras co
        JOIN proveedores pr ON co.proveedor_id = pr.id
        JOIN clientes c ON c.persona_id = pr.persona_id
    """)).scalar()
    print(f"  compras que apuntan a una persona registrada como cliente: {mal}")