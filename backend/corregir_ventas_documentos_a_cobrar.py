"""Corregir la cuenta de Debe de las ventas: Caja → Documentos a cobrar.

    python -X utf8 corregir_ventas_documentos_a_cobrar.py [--ver]

Por qué: una factura es una **deuda del cliente**, no plata recibida. Al contado
o a cuenta corriente, la venta va SIEMPRE a `1.1.03.02 Documentos a cobrar` y
arrastra al cliente como auxiliar. La plata entra recién en tesorería, cuando se
registra el cobro: ahí el Haber va a Documentos a cobrar y el Debe al banco o
caja que corresponda.

`migrar_asientos_automaticos.py` sembraba `VENTA_*_CONTADO` con Caja. Como
`config_asientos` es una tabla (no código), el arreglo es de datos: se corrigen
las filas y las líneas de los asientos que quedaron viejas.

No borra nada. Solo toca:
  - `config_asientos`: 2 filas (VENTA_SERVICIOS_CONTADO, VENTA_ARTICULOS_CONTADO)
  - `asiento_detalle`: líneas con Debe en Caja de asientos que nacieron de una
    factura. Una línea en Caja de OTRO asiento es movimiento de tesorería y no
    se toca.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text  # noqa: E402

from app.database import engine  # noqa: E402

VER = "--ver" in sys.argv
CAJA = "1.1.01.01"
DOC_COBRAR = "1.1.03.02"

# --- el SQL, para verlo antes de correr -------------------------------------
SQL_CONFIG = """\
UPDATE config_asientos
   SET cuenta_debe = <id de 1.1.03.02>
 WHERE clave IN ('VENTA_SERVICIOS_CONTADO', 'VENTA_ARTICULOS_CONTADO');
"""

SQL_ASIENTO = """\
-- El auxiliar va aparte porque cada asiento tiene su cliente: es un UPDATE por
-- asiento, no uno solo para todas las filas.
UPDATE asiento_detalle d
   SET d.id_cuenta     = <id de 1.1.03.02>,
       d.tipo_auxiliar = 'CLIENTE',
       d.id_auxiliar   = <cliente de la factura>
 WHERE d.id_asiento = <asiento>
   AND d.id_cuenta  = <id de 1.1.01.01>   -- solo la línea de Debe en Caja
   AND d.debe > 0;
"""

print("SQL que se va a aplicar (nada de esto borra datos):\n")
print(SQL_CONFIG.strip())
print("\n" + SQL_ASIENTO.strip())

with engine.connect() as conn:
    doc = conn.execute(
        text("SELECT id_cuenta FROM plan_cuentas WHERE codigo = :c"),
        {"c": DOC_COBRAR},
    ).scalar()
    caja = conn.execute(
        text("SELECT id_cuenta FROM plan_cuentas WHERE codigo = :c"),
        {"c": CAJA},
    ).scalar()

    print("\nAntes:")
    for r in conn.execute(
        text(
            "SELECT c.clave, p.codigo FROM config_asientos c "
            "LEFT JOIN plan_cuentas p ON p.id_cuenta = c.cuenta_debe "
            "ORDER BY c.clave"
        )
    ):
        print(f"  {r[0]:<30} debe={r[1]}")

    # Los asientos de factura que tienen el Debe en Caja, con su cliente.
    a_corregir = conn.execute(
        text(
            "SELECT d.id_asiento, o.id_factura, f.cliente_id "
            "  FROM asiento_detalle d "
            "  JOIN asiento_origen o ON o.id_asiento = d.id_asiento "
            "  JOIN facturas f ON f.id = o.id_factura "
            " WHERE o.origen = 'FACTURA' AND d.id_cuenta = :caja AND d.debe > 0"
        ),
        {"caja": caja},
    ).all()

if VER or doc is None or caja is None:
    if doc is None or caja is None:
        raise SystemExit(
            "Falta 1.1.03.02 o 1.1.01.01 en el plan de cuentas. "
            "Cargá el plan primero (migrar_plan_cuentas.py)."
        )
    print(f"\n--ver: no se aplicó nada. {len(a_corregir)} asientos a corregir.")
    raise SystemExit(0)

with engine.begin() as conn:
    n = conn.execute(
        text(
            "UPDATE config_asientos SET cuenta_debe = :doc "
            " WHERE clave IN ('VENTA_SERVICIOS_CONTADO', 'VENTA_ARTICULOS_CONTADO')"
        ),
        {"doc": doc},
    ).rowcount

    for id_asiento, _id_factura, cliente_id in a_corregir:
        conn.execute(
            text(
                "UPDATE asiento_detalle "
                "   SET id_cuenta = :doc, tipo_auxiliar = 'CLIENTE', id_auxiliar = :cli "
                " WHERE id_asiento = :a AND id_cuenta = :caja AND debe > 0"
            ),
            {"doc": doc, "cli": cliente_id, "a": id_asiento, "caja": caja},
        )

print(f"\nconfig_asientos: {n} filas cambiadas a Documentos a cobrar")
print(f"asiento_detalle: {len(a_corregir)} asientos corregidos")

with engine.connect() as conn:
    print("\nconfig_asientos ahora:")
    for r in conn.execute(
        text(
            "SELECT c.clave, p.codigo, p.nombre FROM config_asientos c "
            "LEFT JOIN plan_cuentas p ON p.id_cuenta = c.cuenta_debe ORDER BY c.clave"
        )
    ):
        print(f"  {r[0]:<30} debe={r[1]} {r[2]}")

    print("\nasientos de factura: qué cuenta tiene el Debe")
    for r in conn.execute(
        text(
            "SELECT o.id_factura, a.id_asiento, p.codigo, p.nombre, d.debe, "
            "       d.tipo_auxiliar, d.id_auxiliar "
            "  FROM asiento_origen o "
            "  JOIN asientos a ON a.id_asiento = o.id_asiento "
            "  JOIN asiento_detalle d ON d.id_asiento = a.id_asiento "
            "  JOIN plan_cuentas p ON p.id_cuenta = d.id_cuenta "
            " WHERE o.origen = 'FACTURA' AND d.debe > 0 ORDER BY a.id_asiento"
        )
    ):
        print(
            f"  factura {r[0]:<5} asiento {r[1]:<5} {r[2]} {r[3]:<24} "
            f"{r[4]:>12}  aux={r[5]}/{r[6]}"
        )

print("\nListo. Las facturas nuevas ya salen con Documentos a cobrar, sin tocar código.")