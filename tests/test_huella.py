"""¿La huella digital detecta de verdad que se perdió algo?

La huella es la red de seguridad del 02/10/2026, así que hay que probarla como
se prueba todo en este proyecto: **no alcanza con que funcione, hay que
verificar que avisa**.

La prueba es de riesgo cero: crea una fila temporal en `localidades` que NO
está marcada como prueba (o sea, para la huella es un dato real del contador),
toma la huella con ella presente, la borra, y comprueba que la comparación
avisa que falta. Después no queda nada: la base vuelve a como estaba.

Lo que también se verifica es lo contrario: si la huella está bien, borrar los
restos de una corrida anterior NO tiene que avisar nada.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

from sqlalchemy import text  # noqa: E402

import borrar_prueba  # noqa: E402
from app.database import SessionLocal  # noqa: E402

resultado = []


def chequear(nombre, condicion, detalle=""):
    resultado.append((nombre, bool(condicion), detalle))


db = SessionLocal()

# Limpieza de arranque: si una corrida anterior murió a mitad, estas facturas
# siguen ahí y el UNIQUE de (tipo, punto de venta, número) revienta. La suite
# tiene que ser reentrante.
db.execute(
    text("DELETE FROM facturas WHERE concepto = 'PRUEBA HUELLA' "
         "OR (punto_venta = '9900' AND numero = '00000002')")
)
db.execute(
    text("DELETE FROM localidades WHERE nombre = 'PRUEBA HUELLA'")
)
db.commit()

# --- 1) la huella AVISA cuando falta una fila -------------------------
db.execute(
    text(
        "INSERT INTO localidades (codigo_postal, nombre, provincia) "
        "VALUES ('X001', 'PRUEBA HUELLA', 'TEST')"
    )
)
db.commit()

nueva = db.execute(
    text("SELECT id FROM localidades WHERE nombre = 'PRUEBA HUELLA'")
).scalar()
chequear("Se pudo crear la fila temporal", nueva is not None, str(nueva))

con_la_fila = borrar_prueba.huella(db)
chequear(
    "La fila temporal cuenta como dato real en la huella",
    nueva in con_la_fila["localidades"],
    f"id={nueva}",
)

db.execute(text("DELETE FROM localidades WHERE id = :i"), {"i": nueva})
db.commit()

perdidas = borrar_prueba.comparar(con_la_fila, borrar_prueba.huella(db))
chequear(
    "La huella AVISA que se perdió la fila",
    any("localidades" in p for p in perdidas),
    str(perdidas),
)
chequear(
    "El aviso dice cuántas filas y cuáles",
    any("localidades: 1 fila" in p for p in perdidas),
    str(perdidas),
)

# --- 2) la huella NO avisa si no se perdió nada -----------------------
antes = borrar_prueba.huella(db)
perdidas = borrar_prueba.comparar(antes, borrar_prueba.huella(db))
chequear(
    "Sin pérdidas no hay aviso (no grita por nada)",
    perdidas == [],
    str(perdidas),
)

# --- 3) borrar los restos de una corrida NO es una pérdida -----------
# Esto es lo que más avisos falsos genera: las suites limpian lo suyo al
# terminar, y eso no es perder nada.
db.execute(
    text(
        "INSERT INTO facturas (cliente_id, fecha, tipo_comprobante, punto_venta, "
        "numero, importe, concepto, condicion_venta, estado, tipo_operacion, "
        "neto, iva, creado, actualizado) VALUES "
        "(1, '2026-09-15', 'factura_b', '9900', '00000001', 1000, "
        "'PRUEBA HUELLA', 'contado', 'pendiente', 'B', 1000, 0, NOW(), NOW())"
    )
)
db.commit()
antes_con_prueba = borrar_prueba.huella(db)

# Ahora la suite "limpia" su basura:
nuevas_facturas = [
    r[0] for r in db.execute(
        text("SELECT id FROM facturas WHERE concepto = 'PRUEBA HUELLA'")
    ).all()
]
marcas = ",".join(str(i) for i in nuevas_facturas)
db.execute(text(f"DELETE FROM facturas WHERE id IN ({marcas})"))
db.commit()

perdidas = borrar_prueba.comparar(antes_con_prueba, borrar_prueba.huella(db))
chequear(
    "Borrar una factura de PRUEBA no se cuenta como pérdida",
    perdidas == [],
    str(perdidas),
)

# --- 4) una factura con punto de venta reservado tampoco -------------
db.execute(
    text(
        "INSERT INTO facturas (cliente_id, fecha, tipo_comprobante, punto_venta, "
        "numero, importe, concepto, condicion_venta, estado, tipo_operacion, "
        "neto, iva, creado, actualizado) VALUES "
        "(1, '2026-09-15', 'factura_b', '9900', '00000002', 1000, "
        "'Otra cosa', 'contado', 'pendiente', 'B', 1000, 0, NOW(), NOW())"
    )
)
db.commit()
antes_pv = borrar_prueba.huella(db)
borrar_prueba.limpiar_todo(db)
perdidas = borrar_prueba.comparar(antes_pv, borrar_prueba.huella(db))
chequear(
    "Borrar la factura del punto de venta 9900 tampoco es una pérdida",
    perdidas == [],
    str(perdidas),
)

db.close()

fallos = [r for r in resultado if not r[1]]
for nombre, ok, detalle in resultado:
    if not ok:
        print(f"  FALLA  {nombre}  {detalle}")
print()
print(f"  {len(resultado) - len(fallos)}/{len(resultado)} pruebas correctas")
if not fallos:
    print("  La huella avisa cuando tiene que avisar, y se calla cuando no.")
else:
    print(f"  {len(fallos)} FALLOS")
raise SystemExit(1 if fallos else 0)