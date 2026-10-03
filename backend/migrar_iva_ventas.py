"""
LIBRO DE IVA VENTAS — agrega percepción y conceptos no gravados, y completa el
desglose de las facturas que estaban sin neto.

    python -X utf8 migrar_iva_ventas.py

Idempotente: se puede correr las veces que haga falta.

QUÉ HACE, en tres pasos:

1. Agrega `percepcion` y `no_gravado` a `facturas`. Los dos campos existen en
   `compras` pero no en ventas, y el Libro de IVA los necesita como columna.

2. Pone la alícuota **21%** (la general, `alicuotas_iva.id = 2`) a las facturas
   que no tienen desglose.

3. Calcula `neto` e `iva` de esas facturas: `neto = importe / (1 + alícuota)` con
   **2 decimales**, y `iva = importe - neto`.

   El redondeo a 2 es el que ya usa el sistema: la factura 00000024 tiene
   18000 de total, neto 14876.03 e IVA 3123.97, que es exactamente
   `18000 - 14876.03`. Si se redondeara a 4, daría 14876.0331 y no cuadraría
   con lo que ya está cargado.

QUÉ NO TOCA: las facturas que ya tienen `neto`. Si el contador lo cargó a mano,
o lo cargó el flujo "sin IVA" (neto = importe, IVA = 0), ese número es
intencionado y esta migración no lo pisa. Solo completa las que están en blanco.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import inspect, text

from app.database import engine

# La alícuota general. Va por id y no por porcentaje para no depender del texto
# de `nombre`, que el contador puede cambiar desde Configuración.
ALICUOTA_GENERAL_ID = 2


def columnas_de_facturas() -> set:
    return {c["name"] for c in inspect(engine).get_columns("facturas")}


def paso_1_columnas():
    """Agrega percepcion y no_gravado si no existen."""
    actuales = columnas_de_facturas()
    nuevos = []
    if "percepcion" not in actuales:
        nuevos.append("ADD COLUMN percepcion DECIMAL(16,4) NULL")
    if "no_gravado" not in actuales:
        nuevos.append("ADD COLUMN no_gravado DECIMAL(16,4) NULL")

    if not nuevos:
        print("  paso 1: las columnas ya estaban")
        return

    with engine.begin() as c:
        for sql in nuevos:
            c.execute(text("ALTER TABLE facturas " + sql))
    print("  paso 1: agregadas ->", ", ".join(n.split()[2] for n in nuevos))


def paso_2_alicuota():
    """21% a las facturas que no tienen desglose."""
    with engine.begin() as c:
        n = c.execute(
            text(
                "UPDATE facturas SET alicuota_iva_id = :alic "
                "WHERE neto IS NULL AND alicuota_iva_id IS NULL AND estado <> 'anulada'"
            ),
            {"alic": ALICUOTA_GENERAL_ID},
        ).rowcount
    print("  paso 2: alicuota general en", n, "factura(s)")


def paso_3_neto_iva():
    """Neto e IVA de las que estaban en blanco."""
    with engine.begin() as c:
        filas = c.execute(
            text(
                "SELECT f.id, f.numero, f.importe, a.porcentaje "
                "FROM facturas f JOIN alicuotas_iva a ON a.id = f.alicuota_iva_id "
                "WHERE f.neto IS NULL AND f.estado <> 'anulada' ORDER BY f.id"
            )
        ).all()

        for fid, numero, importe, porcentaje in filas:
            neto = round(float(importe) / (1 + float(porcentaje) / 100), 2)
            iva = round(float(importe) - neto, 2)
            c.execute(
                text(
                    "UPDATE facturas SET neto = :neto, iva = :iva, "
                    "alicuota_iva_aplicada = :alic WHERE id = :id"
                ),
                {"neto": neto, "iva": iva, "alic": float(porcentaje), "id": fid},
            )
            print(f"    factura {numero}: total {importe} -> neto {neto} + iva {iva}")
    print("  paso 3: completadas", len(filas), "factura(s)")


def estado_final():
    with engine.begin() as c:
        print()
        print("  COMO QUEDO:")
        for r in c.execute(
            text(
                "SELECT f.id, f.fecha, f.numero, f.tipo_comprobante, f.importe, "
                "f.neto, f.iva, f.alicuota_iva_aplicada, f.percepcion, f.no_gravado, f.estado "
                "FROM facturas f ORDER BY f.fecha, f.numero"
            )
        ).all():
            print("   ", r)

        incompletas = c.execute(
            text("SELECT COUNT(*) FROM facturas WHERE neto IS NULL AND estado <> 'anulada'")
        ).scalar()
        print()
        print("  facturas sin neto (deben quedar 0):", incompletas)


if __name__ == "__main__":
    print("Migración: Libro de IVA Ventas")
    paso_1_columnas()
    paso_2_alicuota()
    paso_3_neto_iva()
    estado_final()