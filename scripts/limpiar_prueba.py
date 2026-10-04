"""AVISO: este script MODIFICA la base REAL.

    NO lo corras sin leer esto.

Qué hace: `UPDATE personas SET email = NULL WHERE nombre = 'PROVEEDOR'`. Borra el
correo de todas las personas que se llamen PROVEEDOR.

Contra qué base: `app.database` lee `DB_NAME` del entorno. Si no está definida,
usa `gestion_contable` — la del estudio. Para que fuera seguro habría que correrlo
con la variable puesta:

    $env:DB_NAME = "gestion_contable_test"
    python -X utf8 scripts/limpiar_prueba.py

Ojo: el filtro es por NOMBRE, no por un identificador. Si tenés un proveedor real
que se llame PROVEEDOR, le borra el correo. En la base del estudio hoy no hay
ninguna persona con ese nombre (verificado), así que no le haría nada, pero eso
puede cambiar.

Por qué sigue acá: quedó del 01/10/2026, de cuando se estaban limpiando datos de
prueba que se habían mezclado. El cambio ya está aplicado. Si no lo vas a usar
nunca, se puede borrar: Git conserva el historial.
"""

import sys

sys.path.insert(0, r"C:\proyecto-gestion-contable\backend")
from sqlalchemy import text

from app.database import engine

print("Base a la que se conecta:", engine.url.database)

with engine.begin() as conn:
    r = conn.execute(text("SELECT email FROM personas WHERE nombre = :n"), {"n": "PROVEEDOR"}).scalar()
    print("email guardado:", r)
    conn.execute(text("UPDATE personas SET email = NULL WHERE nombre = :n"), {"n": "PROVEEDOR"})
    print("limpiado a null")
