"""Notas de crédito y de débito: códigos internos, asiento invertido y vínculo.

    python -X utf8 migrar_notas_credito.py [--ver]

Por qué: hasta ahora el asiento automático **ignoraba** el tipo de comprobante.
Una nota de crédito tomaba un número de `FV` (Factura de venta) y se asentaba
como si fuera una venta más: Debe en Documentos a cobrar, Haber en Ingresos. Eso
está al revés — una nota de crédito es lo OPUESTO de una factura.

## Qué hace una nota

| | Factura | Nota de crédito |
|---|---|---|
| Documentos a cobrar | **Debe** (le deben a vos) | **Haber** (le devuelves) |
| Ingresos | **Haber** (ganaste) | **Debe** (revertís) |
| IVA a pagar | **Haber** | **Debe** |

Una nota de DÉBITO es lo contrario: Documentos a cobrar en el Haber porque
genera deuda, e Ingresos en el Debe.

## Los 9 tipos de comprobante se agrupan en 3 familias

No hace falta un código interno por cada uno:

| Familia | Qué es | Asiento | Código |
|---|---|---|---|
| Factura A/B/C | venta | DEBE documentos / HABER ingresos | `FV` |
| Nota de crédito A/B/C | baja de venta | HABER documentos / DEBE ingresos | `NC` |
| Nota de débito A/B/C | aumento de venta | HABER documentos / DEBE ingresos | `ND` |

La A, B o C dice ante quién se emitió (fiscalidad), **no** qué pasa
contablemente. Por eso la numeración no se multiplica por tres: la primera nota
de crédito es `NC-000001`, sea A, B o C.

## Qué toca

- `config_comprobantes`: 2 filas nuevas (NC, ND).
- `config_asientos`: 2 claves nuevas (CREDITO_SERVICIOS, DEBITO_SERVICIOS).
- `facturas`: columna `factura_relacionada_id` + su FK, para saber a qué factura
  corrige la nota.
- Borrar la nota de prueba id 84 (era un borrador, confirmado).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text  # noqa: E402

from app.database import engine  # noqa: E402

VER = "--ver" in sys.argv

DOC_COBRAR = "1.1.03.02"
ING_SERVICIOS = "4.2.01"
IVA_PAGAR = "2.1.03.01"
NOTA_BORRAR = 84

SQL = """\
-- 1) Dos códigos internos nuevos
INSERT INTO config_comprobantes (codigo, nombre, origen, activa) VALUES
  ('NC', 'Nota de crédito', 'FACTURA', 1),
  ('ND', 'Nota de débito',   'FACTURA', 1);

-- 2) Dos configuraciones de asiento. Se ve el asiento ya invertido:
--    la nota de crédito pone los INGRESOS en el Debe.
INSERT INTO config_asientos
  (clave, nombre, cuenta_debe, cuenta_haber_ingresos, cuenta_haber_iva, activa)
VALUES
  ('CREDITO_SERVICIOS', 'Nota de crédito por servicios',
   <4.2.01 ingresos>, <1.1.03.02 documentos>, <2.1.03.01 iva>, 1),
  ('DEBITO_SERVICIOS',  'Nota de débito por servicios',
   <1.1.03.02 documentos>, <4.2.01 ingresos>, <2.1.03.01 iva>, 1);

-- 3) La nota dice a qué factura corrige
ALTER TABLE facturas ADD COLUMN factura_relacionada_id INT NULL AFTER cliente_id;
ALTER TABLE facturas ADD CONSTRAINT fk_factura_relacionada
  FOREIGN KEY (factura_relacionada_id) REFERENCES facturas (id)
  ON DELETE RESTRICT ON UPDATE CASCADE;
"""

print("SQL que se va a aplicar (no borra nada salvo la nota 84, que es "
      "un borrador):\n")
print(SQL)


def id_de(conn, codigo):
    return conn.execute(
        text("SELECT id_cuenta FROM plan_cuentas WHERE codigo = :c"), {"c": codigo}
    ).scalar()


with engine.connect() as conn:
    cuentas = {c: id_de(conn, c) for c in (DOC_COBRAR, ING_SERVICIOS, IVA_PAGAR)}

    ya_fc = conn.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.COLUMNS "
            " WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'facturas' "
            "   AND COLUMN_NAME = 'factura_relacionada_id'"
        )
    ).scalar()
    nota = conn.execute(
        text("SELECT id, tipo_comprobante, numero, concepto, importe "
             "  FROM facturas WHERE id = :i"),
        {"i": NOTA_BORRAR},
    ).mappings().first()

print(f"\ncuentas del plan: {cuentas}")
print(f"columna factura_relacionada_id ya existe: {'sí' if ya_fc else 'no'}")
print(f"nota id {NOTA_BORRAR}: {dict(nota) if nota else 'no existe'}")

if any(v is None for v in cuentas.values()):
    raise SystemExit(
        "Falta alguna cuenta del plan (1.1.03.02 / 4.2.01 / 2.1.03.01). "
        "Cargá el plan primero (migrar_plan_cuentas.py)."
    )

if VER:
    print("\n--ver: no se aplicó nada.")
    raise SystemExit(0)

with engine.begin() as conn:
    # --- 1) códigos internos ------------------------------------------------
    for codigo, nombre in (("NC", "Nota de crédito"), ("ND", "Nota de débito")):
        conn.execute(
            text(
                "INSERT INTO config_comprobantes (codigo, nombre, origen, activa) "
                "VALUES (:c, :n, 'FACTURA', 1) "
                "ON DUPLICATE KEY UPDATE nombre = VALUES(nombre), "
                "                       origen = VALUES(origen), activa = 1"
            ),
            {"c": codigo, "n": nombre},
        )
    print("\nconfig_comprobantes: NC y ND cargados")

    # --- 2) configuraciones de asiento --------------------------------------
    # La de crédito va al revés: ingresos en el Debe, documentos en el Haber.
    # OJO: `cuentas` guarda el CÓDIGO ("4.2.01"), y la columna
    # `cuenta_debe` es un id de `plan_cuentas` (INT). Hay que pasar el id, no
    # el código: si se pasa el código, MySQL avisa "Data truncated for column
    # cuenta_debe". Ojo con esto al revisar: siempre ver si la columna es un id
    # o un código.
    ids = {codigo: id_de(conn, codigo)
           for codigo in (DOC_COBRAR, ING_SERVICIOS, IVA_PAGAR)}
    configs = [
        ("CREDITO_SERVICIOS", "Nota de crédito por servicios",
         ids[ING_SERVICIOS], ids[DOC_COBRAR], ids[IVA_PAGAR]),
        ("DEBITO_SERVICIOS", "Nota de débito por servicios",
         ids[DOC_COBRAR], ids[ING_SERVICIOS], ids[IVA_PAGAR]),
    ]
    for clave, nombre, debe, hab_ing, hab_iva in configs:
        conn.execute(
            text(
                "INSERT INTO config_asientos "
                " (clave, nombre, cuenta_debe, cuenta_haber_ingresos, "
                "  cuenta_haber_iva, cuenta_haber_cobranza, activa) "
                "VALUES (:k, :n, :d, :i, :v, NULL, 1) "
                "ON DUPLICATE KEY UPDATE nombre = VALUES(nombre), "
                "  cuenta_debe = VALUES(cuenta_debe), "
                "  cuenta_haber_ingresos = VALUES(cuenta_haber_ingresos), "
                "  cuenta_haber_iva = VALUES(cuenta_haber_iva), activa = 1"
            ),
            {"k": clave, "n": nombre, "d": debe, "i": hab_ing, "v": hab_iva},
        )
    print(f"config_asientos: {len(configs)} configuraciones cargadas")

    # --- 3) columna de vínculo ----------------------------------------------
    # Se consulta information_schema antes de aplicar: si ya existe (porque se
    # corrió dos veces), el ALTER reventaría con "duplicate column name".
    ya = conn.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.COLUMNS "
            " WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'facturas' "
            "   AND COLUMN_NAME = 'factura_relacionada_id'"
        )
    ).scalar()
    if ya:
        print("facturas: la columna factura_relacionada_id ya estaba")
    else:
        conn.execute(
            text("ALTER TABLE facturas "
                 "ADD COLUMN factura_relacionada_id INT NULL AFTER cliente_id")
        )
        conn.execute(
            text(
                "ALTER TABLE facturas ADD CONSTRAINT fk_factura_relacionada "
                "FOREIGN KEY (factura_relacionada_id) REFERENCES facturas (id) "
                "ON DELETE RESTRICT ON UPDATE CASCADE"
            )
        )
        print("facturas: columna factura_relacionada_id + FK agregadas")

    # --- 4) borrar la nota de borrador -------------------------------------
    if nota is not None:
        await_apps = conn.execute(
            text("SELECT COUNT(*) FROM aplicaciones_recibo WHERE factura_id = :i"),
            {"i": NOTA_BORRAR},
        ).scalar()
        if await_apps:
            raise SystemExit(
                f"La nota {NOTA_BORRAR} tiene {await_apps} recibos aplicados. "
                "Deshacelos antes de borrarla."
            )
        conn.execute(text("DELETE FROM facturas WHERE id = :i"), {"i": NOTA_BORRAR})
        print(f"facturas: borrada la nota de borrador id {NOTA_BORRAR}")

print("\n--- cómo quedó ---")
with engine.connect() as conn:
    print("\nconfig_comprobantes (los de origen FACTURA):")
    for r in conn.execute(
        text("SELECT codigo, nombre, origen FROM config_comprobantes "
             " WHERE origen = 'FACTURA' ORDER BY codigo")
    ):
        print(f"  {r[0]:<4} {r[1]}")

    print("\nconfig_asientos: debe → ingresos → iva")
    for r in conn.execute(
        text(
            "SELECT c.clave, cd.codigo, ci.codigo, cv.codigo "
            "  FROM config_asientos c "
            "  LEFT JOIN plan_cuentas cd ON cd.id_cuenta = c.cuenta_debe "
            "  LEFT JOIN plan_cuentas ci ON ci.id_cuenta = c.cuenta_haber_ingresos "
            "  LEFT JOIN plan_cuentas cv ON cv.id_cuenta = c.cuenta_haber_iva "
            " WHERE c.clave LIKE 'CREDITO%' OR c.clave LIKE 'DEBITO%' "
            " ORDER BY c.clave"
        )
    ):
        print(f"  {r[0]:<20} {r[1]} → {r[2]} (+iva {r[3]})")

print("\nListo. Falta el código que use estas cuentas al armar el asiento.")