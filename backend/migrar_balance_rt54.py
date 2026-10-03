# Crea las tablas del Balance RT54. Se corre una vez (es idempotente):
#   python migrar_balance_rt54.py
import sys

sys.path.insert(0, r"C:\proyecto-gestion-contable\backend")
from app.database import Base, engine
from app.models.balance_rt54 import (
    BalanceEjercicio,
    BalanceNota,
    BalanceNotaCelda,
    BalanceValor,
)

Base.metadata.create_all(
    bind=engine,
    tables=[
        BalanceEjercicio.__table__,
        BalanceValor.__table__,
        BalanceNota.__table__,
        BalanceNotaCelda.__table__,
    ],
)
print("Tablas bal_rt54_ejercicios, bal_rt54_valores, bal_rt54_notas y bal_rt54_nota_celdas listas")

# Columnas nuevas de la carátula (registro público, controlante y capital).
# create_all no agrega columnas a tablas ya creadas: se agregan una por una
# solamente si todavía no están.
from sqlalchemy import inspect, text

NUEVAS_COLUMNAS = {
    col.name: str(col.type)
    for col in BalanceEjercicio.__table__.columns
    if col.name
    not in {
        "id", "cliente_id", "nombre", "fecha_inicio", "fecha_fin",
        "entidad", "cuit", "domicilio", "actividad", "actividad_secundaria",
        "creado", "actualizado",
    }
}
actuales = {c["name"] for c in inspect(engine).get_columns("bal_rt54_ejercicios")}
faltantes = {c: t for c, t in NUEVAS_COLUMNAS.items() if c not in actuales}
if faltantes:
    with engine.connect() as conn:
        for columna, tipo in faltantes.items():
            conn.execute(text(f"ALTER TABLE bal_rt54_ejercicios ADD COLUMN {columna} {tipo}"))
        conn.commit()
print(
    "Columnas de carátula agregadas:" if faltantes else "Columnas de carátula: ya estaban",
    ", ".join(faltantes) or "(ninguna)",
)
