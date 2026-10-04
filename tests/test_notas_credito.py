"""Notas de crédito y de débito: el asiento al revés y su propia numeración.

    python -X utf8 test_notas_credito.py

El 02/10/2026 el contador intentó cargar una nota de crédito y no funcionó: la
pantalla mostraba el asiento de una VENTA (Documentos a cobrar en el Debe,
Ingresos en el Haber) y el comprobante salía como `FV-000007`, o sea que la nota
se comía un número de factura. Dos errores en uno, y los dos difíciles de ver
sin mirar el número.

Lo que se verifica acá:
  1. La nota de crédito tiene el asiento **al revés** de la venta.
  2. La nota de débito hace lo mismo que la factura.
  3. Cada familia toma su código: FV, NC, ND. La numeración no se mezclan.
  4. El monto va POR CUENTA: documentos lleva el total (con IVA), ingresos el
     neto, IVA a pagar el IVA. Si se invirtiera solo el lado, el asiento no
     cierra.
  5. El preview y el asiento REAL dan lo mismo.
  6. La nota dice a qué factura corrige, y el backend valida el cliente.
  7. No hay asiento de nota que toque Caja (como las ventas, §4.36).
"""

import json
import os
import sys
import urllib.error
import urllib.request
from decimal import Decimal
# La dirección de la API sale de `GC_BASE_URL` para poder correr estas pruebas
# contra la base de PRUEBAS y no contra la del estudio. Si la variable no
# está, usa 8010 como antes: no cambia cómo se corren.

BASE = os.environ.get("GC_BASE_URL", "http://127.0.0.1:8010")
ok = 0
fallos = []
_RUTA_BACKEND = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
)
sys.path.insert(0, _RUTA_BACKEND)

TIPO_COMPROBANTE = "factura_b"
IVA_TOTAL = Decimal("121000.00")
IVA_NETO = Decimal("100000.00")
IVA_IMPUESTO = Decimal("21000.00")

# Lo que este test creó, para borrarlo al final.
CREADAS = []


def req(metodo, ruta, datos=None, token=None):
    r = urllib.request.Request(BASE + ruta, method=metodo)
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", "Bearer " + token)
    cuerpo = json.dumps(datos).encode() if datos is not None else None
    try:
        with urllib.request.urlopen(r, cuerpo, timeout=30) as resp:
            t = resp.read().decode()
            return resp.status, json.loads(t) if t else None
    except urllib.error.HTTPError as e:
        t = e.read().decode() or "{}"
        try:
            return e.code, json.loads(t)
        except json.JSONDecodeError:
            return e.code, {"detail": t}


def check(nombre, cond, detalle=""):
    global ok
    if cond:
        ok += 1
        print(f"  OK  {nombre}")
    else:
        fallos.append(nombre)
        print(f"FALLA {nombre} -> {detalle}")


from sqlalchemy import bindparam, text  # noqa: E402

# Esta suite habla con la base de DOS maneras: por HTTP (`BASE`) y por SQL
# directo (`app.database`, para limpiar lo que dejó la corrida). Con solo
# `GC_BASE_URL` el SQL se va a la base REAL y la limpieza no borra nada de la base
# de pruebas.
#
# `DB_NAME` tiene que estar puesta ANTES de que se importe `app.database`, porque
# ese módulo lee el entorno UNA sola vez al importarse. Por eso este bloque va
# arriba del archivo, en el nivel del módulo, y no adentro de la función que
# limpia.
if "GC_BASE_URL" in os.environ:
    os.environ.setdefault(
        "DB_NAME", os.environ.get("GC_TEST_DB", "gestion_contable_test")
    )

from app.database import SessionLocal  # noqa: E402

st, tok = req("POST", "/api/auth/login", {"usuario": "admin", "password": "admin123"})
token = tok.get("access_token")
check("login", st == 200 and token, str(st))

st, cli = req("GET", "/api/clientes", token=token)
cliente = next((c for c in cli if c.get("cuit") or c.get("dni")), None)
check("hay un cliente para probar", cliente is not None, "no hay clientes")
CLIENTE = cliente["id"]

st, alis = req("GET", "/api/alicuotas-iva", token=token)
IVA21 = next((a for a in alis if float(a["porcentaje"]) == 21.0), None)
check("hay alícuota de 21%", IVA21 is not None, str(alis)[:120])

# Números de comprobante libres: se buscan contra lo que ya existe.
db = SessionLocal()
usados = {r[0] for r in db.execute(text("SELECT numero FROM facturas")).all()}
db.close()
N_FACTURA = next(f"{n:08d}" for n in range(900, 999) if f"{n:08d}" not in usados)
N_NC = f"{int(N_FACTURA) + 1:08d}"
N_ND = f"{int(N_FACTURA) + 2:08d}"

BASE_DATOS = {
    "cliente_id": CLIENTE,
    "fecha": "2026-10-02",
    "punto_venta": "0001",
    "condicion_venta": "cta_corriente_30",
    "tipo_operacion": "SERVICIOS",
    "alicuota_iva_id": IVA21["id"],
}

# =====================================================================
print("\n== 1. La configuración: cada familia con su código y sus cuentas ==")

st, codigos = req("GET", "/api/config-comprobantes", token=token)
por_codigo = {c["codigo"]: c for c in codigos}
for cod in ("FV", "NC", "ND"):
    check(f"el código {cod} existe", cod in por_codigo, str(sorted(por_codigo)))
    check(f"  y es de origen FACTURA",
          cod in por_codigo and por_codigo[cod]["origen"] == "FACTURA",
          str(por_codigo.get(cod, {}).get("origen")))

st, conf = req("GET", "/api/config-asientos", token=token)
filas = {f["clave"]: f for f in conf}
check("las 4 ventas siguen en Documentos a cobrar",
      all(filas[k]["debe_codigo"] == "1.1.03.02"
          for k in filas if k.startswith("VENTA_")),
      str({k: v["debe_codigo"] for k, v in filas.items() if k.startswith("VENTA_")}))
check("la nota de crédito tiene INGRESOS en el Debe",
      filas.get("CREDITO_SERVICIOS", {}).get("debe_codigo") == "4.2.01",
      str(filas.get("CREDITO_SERVICIOS")))
check("  y DOCUMENTOS en el Haber (al revés)",
      filas.get("CREDITO_SERVICIOS", {}).get("ing_codigo") == "1.1.03.02",
      str(filas.get("CREDITO_SERVICIOS")))
check("la nota de DÉBITO va como la venta (documentos en el Debe)",
      filas.get("DEBITO_SERVICIOS", {}).get("debe_codigo") == "1.1.03.02"
      and filas.get("DEBITO_SERVICIOS", {}).get("ing_codigo") == "4.2.01",
      str(filas.get("DEBITO_SERVICIOS")))


# =====================================================================
def preview(tipo, numero, **extra):
    st, r = req("POST", "/api/facturas/preview-asiento",
                {**BASE_DATOS, "tipo_comprobante": tipo, "numero": numero,
                 "importe": float(IVA_TOTAL), "concepto": f"Prueba {tipo}",
                 **extra},
                token=token)
    return st, r


def por_codigo_lineas(r):
    return {l["codigo"]: l for l in r["lineas"]}


# ---------------------------------------------------------------- venta
print("\n== 2. La VENTA: el asiento de referencia ==")
st, pv = preview(TIPO_COMPROBANTE, N_FACTURA)
check("el preview responde 200", st == 200, f"{st} {str(pv)[:120]}")
check("el código es FV", pv["codigo_comprobante"] == "FV", str(pv["codigo_comprobante"]))
lv = por_codigo_lineas(pv)
check("documentos a cobrar en el DEBE, con el total",
      Decimal(str(lv["1.1.03.02"]["debe"])) == IVA_TOTAL
      and Decimal(str(lv["1.1.03.02"]["haber"])) == 0,
      f"{lv['1.1.03.02']['debe']}/{lv['1.1.03.02']['haber']}")
check("ingresos en el HABER, con el neto",
      Decimal(str(lv["4.2.01"]["haber"])) == IVA_NETO, str(lv["4.2.01"]["haber"]))
check("IVA a pagar en el HABER",
      Decimal(str(lv["2.1.03.01"]["haber"])) == IVA_IMPUESTO,
      str(lv["2.1.03.01"]["haber"]))
check("cierra", pv["cierra"] is True, str(pv.get("cierra")))

# --------------------------------------------------------- nota crédito
print("\n== 3. La NOTA DE CRÉDITO: el mismo importe, al revés ==")
st, pnc = preview("nota_credito_a", N_NC)
check("el preview responde 200", st == 200, f"{st} {str(pnc)[:120]}")
check("el código es NC, NO FV (este era el error)",
      pnc["codigo_comprobante"] == "NC", str(pnc["codigo_comprobante"]))
check("y su número tentativo empieza con NC-",
      str(pnc["numero_completo_tentativo"]).startswith("NC-"),
      str(pnc["numero_completo_tentativo"]))
lnc = por_codigo_lineas(pnc)
check("documentos a cobrar en el HABER, con el total",
      Decimal(str(lnc["1.1.03.02"]["haber"])) == IVA_TOTAL
      and Decimal(str(lnc["1.1.03.02"]["debe"])) == 0,
      f"{lnc['1.1.03.02']['debe']}/{lnc['1.1.03.02']['haber']}")
check("ingresos en el DEBE, con el NETO (no el total)",
      Decimal(str(lnc["4.2.01"]["debe"])) == IVA_NETO
      and Decimal(str(lnc["4.2.01"]["haber"])) == 0,
      f"{lnc['4.2.01']['debe']}/{lnc['4.2.01']['haber']}")
check("IVA a pagar también en el DEBE (se revierte con los ingresos)",
      Decimal(str(lnc["2.1.03.01"]["debe"])) == IVA_IMPUESTO
      and Decimal(str(lnc["2.1.03.01"]["haber"])) == 0,
      f"{lnc['2.1.03.01']['debe']}/{lnc['2.1.03.01']['haber']}")
check("NO es idéntico a la venta (tiene que estar al revés)",
      pnc["lineas"] != pv["lineas"], "es el mismo asiento")
check("el auxiliar CLIENTE sigue en Documentos a cobrar",
      lnc["1.1.03.02"].get("tipo_auxiliar") == "CLIENTE",
      str(lnc["1.1.03.02"].get("tipo_auxiliar")))
check("cierra", pnc["cierra"] is True, str(pnc.get("cierra")))
check("el preview dice que es una nota de crédito",
      pnc.get("familia") == "CREDITO", str(pnc.get("familia")))
check("y NO toca Caja ni Fondo fijo",
      not ({"1.1.01.01", "1.1.01.02"} & set(lnc)),
      str(sorted(lnc)))

# ---------------------------------------------------------- nota débito
print("\n== 4. La NOTA DE DÉBITO: como la venta, no al revés ==")
st, pnd = preview("nota_debito_b", N_ND)
check("el preview responde 200", st == 200, f"{st} {str(pnd)[:120]}")
check("el código es ND", pnd["codigo_comprobante"] == "ND", str(pnd["codigo_comprobante"]))
lnd = por_codigo_lineas(pnd)
check("documentos a cobrar en el DEBE (aumenta la deuda)",
      Decimal(str(lnd["1.1.03.02"]["debe"])) == IVA_TOTAL, str(lnd["1.1.03.02"]["debe"]))
check("ingresos en el HABER",
      Decimal(str(lnd["4.2.01"]["haber"])) == IVA_NETO, str(lnd["4.2.01"]["haber"]))
check("cierra", pnd["cierra"] is True, str(pnd.get("cierra")))

# =====================================================================
print("\n== 5. Las tres familias NO comparten numeración ==")
check("la venta toma FV", pv["codigo_comprobante"] == "FV", str(pv["codigo_comprobante"]))
check("la nota de crédito toma NC", pnc["codigo_comprobante"] == "NC",
      str(pnc["codigo_comprobante"]))
check("la nota de débito toma ND", pnd["codigo_comprobante"] == "ND",
      str(pnd["codigo_comprobante"]))
# Lo que se rompe sin esto: la nota se lleva el FV-000008 y la factura siguiente
# quedaría en FV-000007, con un número ya usado.
numeros = {pv["codigo_comprobante"], pnc["codigo_comprobante"],
           pnd["codigo_comprobante"]}
check("son tres códigos distintos", len(numeros) == 3, str(numeros))

# =====================================================================
print("\n== 6. Guardar de verdad: el asiento real tiene que ser el del preview ==")

st, f = req("POST", "/api/facturas",
            {**BASE_DATOS, "tipo_comprobante": TIPO_COMPROBANTE,
             "numero": N_FACTURA, "importe": float(IVA_TOTAL),
             "concepto": "Prueba venta base"},
            token=token)
check("la factura base se guardó", st == 201, f"{st} {str(f)[:120]}")
CREADAS.append(f.get("id"))
ORIGEN = f.get("id")

st, nc = req("POST", "/api/facturas",
             {**BASE_DATOS, "tipo_comprobante": "nota_credito_a",
              "numero": N_NC, "importe": float(IVA_TOTAL),
              "concepto": "Prueba nota de crédito",
              "factura_relacionada_id": ORIGEN},
             token=token)
check("la nota de crédito se guardó", st == 201, f"{st} {str(nc)[:150]}")
CREADAS.append(nc.get("id"))
check("guarda a qué factura corrige",
      nc.get("factura_relacionada_id") == ORIGEN,
      str(nc.get("factura_relacionada_id")))
check("el asiento quedó CONTABILIZADO",
      nc.get("estado_asiento") == "CONTABILIZADO", str(nc.get("estado_asiento")))
check("y su comprobante es NC-",
      str(nc.get("numero_comprobante_asiento")).startswith("NC-"),
      str(nc.get("numero_comprobante_asiento")))

# Si no tiene asiento, seguir con `nc['id_asiento']` revienta con KeyError y
# el error dice menos que "no se generó el asiento".
if not nc.get("id_asiento"):
    check("la nota tiene asiento", False, "no vino id_asiento en la respuesta")
    raise SystemExit(f"\n{ok} OK / {len(fallos) + 1} fallos")

st, a = req("GET", f"/api/asientos/{nc['id_asiento']}", token=token)
real = {d["codigo"]: d for d in a["detalle"]}
check("el asiento REAL va al revés, como el preview",
      Decimal(str(real["1.1.03.02"]["haber"])) == IVA_TOTAL
      and Decimal(str(real["4.2.01"]["debe"])) == IVA_NETO,
      f"{real['1.1.03.02']} / {real['4.2.01']}")
check("y los montos son los mismos cuenta por cuenta",
      all(Decimal(str(real[k]["debe"])) == Decimal(str(lnc[k]["debe"]))
          and Decimal(str(real[k]["haber"])) == Decimal(str(lnc[k]["haber"]))
          for k in lnc),
      "el preview y el asiento difieren")
check("el total coincide con el preview",
      Decimal(str(a["total_debe"])) == Decimal(str(pnc["total_debe"])),
      f"{a['total_debe']} vs {pnc['total_debe']}")
check("y el asiento cierra", Decimal(str(a["total_debe"])) == Decimal(str(a["total_haber"])),
      f"{a['total_debe']} vs {a['total_haber']}")

# =====================================================================
print("\n== 7. Validar la factura a la que corrige ==")

st, r = req("POST", "/api/facturas",
            {**BASE_DATOS, "tipo_comprobante": "nota_credito_a",
             "numero": f"{int(N_NC) + 10:08d}", "importe": 1000.0,
             "concepto": "Prueba sin factura",
             "factura_relacionada_id": 999999},
            token=token)
check("corregir una factura inexistente -> 400", st == 400, f"{st} {str(r)[:120]}")

otro = next((c for c in cli if c["id"] != CLIENTE and (c.get("cuit") or c.get("dni"))), None)
if otro:
    st, r = req("POST", "/api/facturas",
                {**BASE_DATOS, "cliente_id": otro["id"],
                 "tipo_comprobante": "nota_credito_a",
                 "numero": f"{int(N_NC) + 11:08d}", "importe": 1000.0,
                 "concepto": "Prueba otro cliente",
                 "factura_relacionada_id": ORIGEN},
                token=token)
    check("corregir una factura de OTRO cliente -> 400", st == 400,
          f"{st} {str(r)[:120]}")

    st, r = req("POST", "/api/facturas",
                {**BASE_DATOS, "tipo_comprobante": "nota_credito_a",
                 "numero": f"{int(N_NC) + 12:08d}", "importe": 1000.0,
                 "concepto": "Prueba nota contra nota",
                 "factura_relacionada_id": nc["id"]},
                token=token)
    check("corregir a OTRA NOTA (no a una factura) -> 400", st == 400,
          f"{st} {str(r)[:120]}")

st, cg = req("GET", "/api/control-general", token=token)
check("el control general sigue ok", cg["ok"] is True, str(cg["problemas"])[:200])

# =====================================================================
print("\n== 8. Limpiar lo que creó este test ==")
# Con asiento no se borran por la API (409, a propósito). Se borra acotado a
# estas facturas, con su asiento, para no tocar las reales.
#
# **El orden importa**: la nota tiene `factura_relacionada_id` apuntando a la
# factura que corrige (FK `fk_factura_relacionada`, ON DELETE RESTRICT). Si se
# borra la factura original primero, MySQL rebota con "Cannot delete or update
# a parent row". Por eso van al revés: primero las notas, después las facturas.
#
# Se usa `reversed()` sobre CREADAS porque ahí se fueron guardando en el orden
# en que se crearon, y la nota siempre viene después de su factura.
db = SessionLocal()
try:
    for fid in reversed([f for f in CREADAS if f]):
        for aid in [
            r[0] for r in db.execute(
                text("SELECT id_asiento FROM asiento_origen WHERE id_factura = :f"),
                {"f": fid},
            )
        ]:
            for sql in ("DELETE FROM asiento_detalle WHERE id_asiento = :a",
                        "DELETE FROM asiento_origen WHERE id_asiento = :a",
                        "DELETE FROM asientos WHERE id_asiento = :a"):
                db.execute(text(sql), {"a": aid})
        db.execute(text("DELETE FROM facturas WHERE id = :f"), {"f": fid})
    db.commit()
finally:
    db.close()

# Se comprueba con un COUNT: si el borrado falló en silencio, el test avisa.
# Ojo con `IN :ids` sin `expanding=True`: con una lista de N elementos SQLAlchemy
# la trata como un SOLO parámetro y MySQL avisa "not enough arguments".
db = SessionLocal()
try:
    quedan = db.execute(
        text("SELECT COUNT(*) FROM facturas WHERE id IN :ids").bindparams(
            bindparam("ids", expanding=True)
        ),
        {"ids": [f for f in CREADAS if f]},
    ).scalar()
finally:
    db.close()
check("no quedó ninguna de las facturas del test", quedan == 0, str(quedan))
st, cg = req("GET", "/api/control-general", token=token)
check("el control general sigue ok después de borrar", cg["ok"] is True,
      str(cg["problemas"])[:200])

print(f"\n{ok} OK / {len(fallos)} fallos")
if fallos:
    raise SystemExit(1)