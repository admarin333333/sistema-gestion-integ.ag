# Índices de moneda homogénea + fecha de cierre de ejercicio en el cliente.
# Idempotente: se puede correr todas las veces que haga falta.
#   python migrar_indices_moneda.py
import sys

sys.path.insert(0, r"C:\proyecto-gestion-contable\backend")
from sqlalchemy import inspect, text

from app.database import Base, engine
from app.models.indice import IndiceMoneda

Base.metadata.create_all(bind=engine, tables=[IndiceMoneda.__table__])
print("Tabla config_indices_moneda lista")

insp = inspect(engine)
actuales = {c["name"] for c in insp.get_columns("clientes")}
if "fecha_cierre_ejercicio" not in actuales:
    with engine.connect() as conn:
        conn.execute(
            text("ALTER TABLE clientes ADD COLUMN fecha_cierre_ejercicio DATE NULL")
        )
        conn.commit()
    print("Columna clientes.fecha_cierre_ejercicio agregada")
else:
    print("Columna clientes.fecha_cierre_ejercicio: ya estaba")
