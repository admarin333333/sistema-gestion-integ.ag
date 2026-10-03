"""Borrar la factura de prueba 751 ("lop") con su asiento 367.

    python -X utf8 borrar_factura_prueba_751.py [--ver]

Es una factura de prueba que el usuario confirmó que se puede borrar. Una
factura con asiento NO se borra por la API a propósito (409): el asiento es
documento contable. Como acá es de prueba y el usuario lo pidió explícitamente,
se borra por SQL: primero guarda un respaldo y recién después toca.

El orden importa por las claves foráneas: detalle → origen → saldos → asientos
→ comprobante interno → factura.
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text  # noqa: E402

from app.database import engine  # noqa: E402

VER = "--ver" in sys.argv
FACTURA = 751
ASIENTO = 367

PASOS = [
    ("asiento_detalle", "DELETE FROM asiento_detalle WHERE id_asiento = :a"),
    ("asiento_origen", "DELETE FROM asiento_origen WHERE id_asiento = :a"),
    ("asientos", "DELETE FROM asientos WHERE id_asiento = :a"),
    ("facturas", "DELETE FROM facturas WHERE id = :f"),
]

TABLAS_RESPALDO = ["facturas", "asientos", "asiento_detalle", "asiento_origen"]

print("Esto es lo que se va a borrar (factura de prueba):\n")
for tabla, sql in PASOS:
    print(f"  -- {tabla}\n  {sql}")
print(
    "\nEl comprobante interno NO se borra: queda sin asiento y su número no se "
    "reutiliza, que es lo correcto para que no haya dos comprobantes con el "
    "mismo número."
)

if VER:
    print("\n--ver: no se borró nada.")
    raise SystemExit(0)

# --- respaldo ---------------------------------------------------------------
respaldo_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "respaldos")
os.makedirs(respaldo_dir, exist_ok=True)
sello = datetime.now().strftime("%Y%m%d_%H%M%S")
ruta = os.path.join(respaldo_dir, f"factura_{FACTURA}_asiento_{ASIENTO}_{sello}.sql")

with engine.connect() as conn:
    # Si la factura tuviera un recibo o un anticipo aplicado, el borrado
    # rebotaría por la clave foránea. Se avisa antes, no después.
    pend = conn.execute(
        text(
            "SELECT (SELECT COUNT(*) FROM aplicaciones_recibo WHERE factura_id = :f)"
            "     + (SELECT COUNT(*) FROM aplicaciones_anticipo WHERE factura_id = :f)"
        ),
        {"f": FACTURA},
    ).scalar()
    if pend:
        raise SystemExit(
            f"La factura {FACTURA} tiene {pend} aplicaciones (recibos/anticipos). "
            "Deshacelas antes de borrarla."
        )

    filas = []
    for t in TABLAS_RESPALDO:
        if t == "facturas":
            filas_t = conn.execute(
                text("SELECT * FROM facturas WHERE id = :f"), {"f": FACTURA}
            ).mappings().all()
        else:
            filas_t = conn.execute(
                text(f"SELECT * FROM {t} WHERE id_asiento = :a"), {"a": ASIENTO}
            ).mappings().all()
        filas.append((t, filas_t))

sello = datetime.now().strftime("%Y%m%d_%H%M%S")
ruta = os.path.join(respaldo_dir, f"factura_{FACTURA}_asiento_{ASIENTO}_{sello}.sql")

lineas = [
    f"-- Respaldo de la factura {FACTURA} y el asiento {ASIENTO}",
    f"-- {datetime.now():%Y-%m-%d %H:%M:%S}",
    "",
]
for t, filas_t in filas:
    lineas.append(f"-- {t}: {len(filas_t)} filas")
    for fila in filas_t:
        cols = ", ".join(fila.keys())
        vals = ", ".join(f"'{str(v)}'" for v in fila.values())
        lineas.append(f"INSERT INTO {t} ({cols}) VALUES ({vals});")
    lineas.append("")

with open(ruta, "w", encoding="utf-8") as fh:
    fh.write("\n".join(lineas))
print(f"\nRespaldo escrito en:\n  {ruta}")

# --- borrar -----------------------------------------------------------------
with engine.begin() as conn:
    for tabla, sql in PASOS:
        params = {"a": ASIENTO} if ":a" in sql else {"f": FACTURA}
        n = conn.execute(text(sql), params).rowcount
        print(f"  {tabla}: {n} filas borradas")

    # El comprobante interno quedó huérfano; su número no se vuelve a usar.
    comp = conn.execute(
        text(
            "SELECT ci.id_comprobante, ci.codigo_comprobante, ci.numero "
            "  FROM comprobantes_internos ci "
            " WHERE NOT EXISTS (SELECT 1 FROM asientos a "
            "                    WHERE a.id_comprobante = ci.id_comprobante)"
        )
    ).mappings().all()
    for c in comp:
        print(
            f"  comprobante {c['codigo_comprobante']}-{c['numero']} "
            f"(id {c['id_comprobante']}) queda sin asiento: su número NO se "
            "reutiliza, que es lo correcto"
        )

with engine.connect() as conn:
    print("\ncontrol general:")
    total = conn.execute(text("SELECT COUNT(*) FROM asientos")).scalar()
    print(f"  asientos que quedan: {total}")
    caja = conn.execute(
        text(
            "SELECT COALESCE(SUM(d.debe - d.haber), 0) "
            "  FROM asiento_detalle d "
            "  JOIN plan_cuentas p ON p.id_cuenta = d.id_cuenta "
            " WHERE p.codigo = '1.1.01.01'"
        )
    ).scalar()
    print(f"  saldo de Caja: {caja}")
    debe = conn.execute(
        text(
            "SELECT COALESCE(SUM(d.debe), 0), COALESCE(SUM(d.haber), 0) FROM asiento_detalle d"
        )
    ).one()
    print(f"  debe total = {debe[0]} | haber total = {debe[1]}")

print("\nListo. El respaldo está arriba por si hay que volver atrás.")