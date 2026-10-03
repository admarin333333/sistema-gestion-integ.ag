"""Borrar la factura de prueba del asiento al contado (id 805 / asiento 441).

    python -X utf8 borrar_factura_prueba_805.py [--ver]

Es la factura que se cargó desde el navegador para comprobar que al contado va
a Documentos a cobrar. Tiene asiento, así que la API la rechaza con 409 (a
propósito). Como es de prueba y se confirmó, se borra por SQL, con respaldo
antes.

Orden por claves foráneas: detalle → origen → asientos → facturas.
El comprobante interno queda huérfano y su número no se reutiliza, que es lo
correcto: no puede haber dos comprobantes FV con el mismo número.
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text  # noqa: E402

from app.database import engine  # noqa: E402

VER = "--ver" in sys.argv
FACTURA = 805

PASOS = [
    ("asiento_detalle", "DELETE FROM asiento_detalle WHERE id_asiento = :a"),
    ("asiento_origen", "DELETE FROM asiento_origen WHERE id_asiento = :a"),
    ("asientos", "DELETE FROM asientos WHERE id_asiento = :a"),
    ("facturas", "DELETE FROM facturas WHERE id = :f"),
]
TABLAS = ["facturas", "asientos", "asiento_detalle", "asiento_origen"]

with engine.connect() as conn:
    factura = conn.execute(
        text("SELECT * FROM facturas WHERE id = :f"), {"f": FACTURA}
    ).mappings().first()
    if factura is None:
        raise SystemExit(f"La factura {FACTURA} no existe. No hay nada que borrar.")

    asiento = conn.execute(
        text("SELECT id_asiento FROM asiento_origen WHERE id_factura = :f"),
        {"f": FACTURA},
    ).scalar()

    filas = []
    for t in TABLAS:
        if t == "facturas":
            filas.append((t, [factura]))
        elif asiento is not None:
            filas.append(
                (t, conn.execute(
                    text(f"SELECT * FROM {t} WHERE id_asiento = :a"), {"a": asiento}
                ).mappings().all())
            )
        else:
            filas.append((t, []))

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

print(f"Factura {FACTURA} · asiento {asiento}\n")
print("Esto es lo que se va a borrar:\n")
for tabla, sql in PASOS:
    print(f"  -- {tabla}\n  {sql}")
print(
    "\nEl comprobante interno NO se borra: queda sin asiento y su número no se "
    "reutiliza, que es lo correcto."
)

if VER:
    print("\n--ver: no se borró nada.")
    raise SystemExit(0)

respaldo_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "respaldos")
os.makedirs(respaldo_dir, exist_ok=True)
sello = datetime.now().strftime("%Y%m%d_%H%M%S")
ruta = os.path.join(respaldo_dir, f"factura_{FACTURA}_{sello}.sql")

lineas = [
    f"-- Respaldo de la factura {FACTURA} y el asiento {asiento}",
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

with engine.begin() as conn:
    for _tabla, sql in PASOS:
        params = {"a": asiento} if ":a" in sql else {"f": FACTURA}
        n = conn.execute(text(sql), params).rowcount
        print(f"  {_tabla}: {n} filas borradas")

with engine.connect() as conn:
    comp = conn.execute(
        text(
            "SELECT ci.codigo_comprobante, ci.numero FROM comprobantes_internos ci "
            " WHERE NOT EXISTS (SELECT 1 FROM asientos a "
            "                    WHERE a.id_comprobante = ci.id_comprobante)"
        )
    ).mappings().all()
    for c in comp:
        print(f"  comprobante {c['codigo_comprobante']}-{c['numero']} queda sin "
              "asiento: su número NO se reutiliza")
    debe, haber = conn.execute(
        text("SELECT COALESCE(SUM(debe),0), COALESCE(SUM(haber),0) FROM asiento_detalle")
    ).one()
    print(f"\ndebe total = {debe} | haber total = {haber}")

print("\nListo.")