"""Agrega calle + numero_calle a clientes (reemplazan a domicilio)."""

from sqlalchemy import text

from app.database import engine

with engine.begin() as conn:
    cols = {r[0] for r in conn.execute(text("SHOW COLUMNS FROM clientes"))}
    if "calle" not in cols:
        conn.execute(text("ALTER TABLE clientes ADD COLUMN calle VARCHAR(30) NULL"))
        print("+ columna calle")
    else:
        print("= columna calle ya existe")
    if "numero_calle" not in cols:
        conn.execute(text("ALTER TABLE clientes ADD COLUMN numero_calle VARCHAR(10) NULL"))
        print("+ columna numero_calle")
    else:
        print("= columna numero_calle ya existe")
print("Listo.")
