"""La cuenta de cobro fija y el Mayor General.

    python -X utf8 test_mayor_cuenta_cobro.py

1. El recibo toma la cuenta fija de Configuración sin que se le pregunte.
2. Si el recibo trae la suya, gana la suya.
3. El mayor general muestra los movimientos con el saldo acumulado.
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


st, tok = req("POST", "/api/auth/login", {"usuario": "admin", "password": "admin123"})
token = tok.get("access_token")
check("login", st == 200 and token, str(st))

from sqlalchemy import text  # noqa: E402
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
import borrar_prueba  # noqa: E402


def _borrar_recibos(db, ids):
    """Borra los recibos indicados, con su asiento primero.

    El `DELETE /api/recibos/{id}` por API **no funciona** en estos: el recibo ya
    tiene asiento contabilizado y `asiento_origen` apunta al recibo con
    RESTRICT, así que la API devuelve 409. La suite no miraba el código de
    respuesta y los recibos se fugaban en cada corrida: al cabo de un rato
    había 48 recibos de prueba sobre la cuenta corriente del cliente, que
    rompía los mayor de las demás suites.

    El orden lo manda el FK: detalle → origen → asiento → recibo.
    """
    if not ids:
        return 0
    marcas = ",".join(str(i) for i in ids)
    for (aid,) in db.execute(
        text(f"SELECT id_asiento FROM asiento_origen WHERE id_recibo IN ({marcas})")
    ).all():
        db.execute(text("DELETE FROM asiento_detalle WHERE id_asiento = :a"), {"a": aid})
        db.execute(text("DELETE FROM asiento_origen WHERE id_asiento = :a"), {"a": aid})
        db.execute(text("DELETE FROM asientos WHERE id_asiento = :a"), {"a": aid})
    db.execute(text(f"DELETE FROM aplicaciones_recibo WHERE recibo_id IN ({marcas})"))
    db.execute(text(f"DELETE FROM recibo_pagos WHERE recibo_id IN ({marcas})"))
    db.execute(text(f"DELETE FROM recibos WHERE id IN ({marcas})"))
    db.commit()
    return len(ids)


def _limpiar(db):
    """Borra lo que dejaron corridas anteriores.

    SOLO las facturas del punto de venta reservado '9955' y los asientos que
    salen de ellas. Las tres líneas que había antes (`DELETE FROM asientos`,
    `DELETE FROM asiento_origen`, `DELETE FROM comprobantes_internos` a secas)
    borraban los asientos reales del contador en cada corrida. Ver
    `borrar_prueba.py`.

    OJO: acá NO va `borrar_prueba.limpiar_todo()`. Esta suite cuenta los
    movimientos del Mayor de documentos a cobrar y espera ver exactamente los
    suyos; si la limpieza se lleva también lo de otras suites el número le da
    bien, y si no se lleva nada el número le da mal. Lo que tiene que_no_
    pasar es que queden asientos sueltos de la corrida anterior, y para eso
    alcanza con borrar las facturas de '9955' y lo que cuelga de ellas.
    """
    facturas = [
        r[0]
        for r in db.execute(
            text("SELECT id FROM facturas WHERE punto_venta = '9955'")
        ).all()
    ]
    borrar_prueba.limpiar_asientos(db, facturas)
    borrar_prueba.limpiar_comprobantes(db)
    if facturas:
        marcas = ",".join(str(i) for i in facturas)
        db.execute(text(f"DELETE FROM facturas WHERE id IN ({marcas})"))
    db.commit()


_db = SessionLocal()
_limpiar(_db)
_db.close()

st, plan = req("GET", "/api/plan-cuentas", token=token)
IDS = {c["codigo"]: c["id_cuenta"] for c in plan}
BANCO, CAJA = IDS["1.1.01.03"], IDS["1.1.01.01"]

print("\n== La cuenta de cobro fija ==")
st, fija = req("GET", "/api/ejercicios/cuenta-cobro-fija", token=token)
check("hay una cuenta de cobro fija", st == 200 and fija["id_cuenta"],
      f"{st} {str(fija)[:120]}")
check("es una cuenta del plan (tiene código)", fija["codigo"] is not None,
      str(fija))
print(f"     cuenta fija: {fija['codigo']} {fija['nombre']}")

# El estado original, para restaurarlo al final.
ORIGINAL = fija["id_cuenta"]

st, clientes = req("GET", "/api/clientes", token=token)
CLIENTE = next((c for c in clientes if c.get("cuit")), clientes[0])
CID = CLIENTE["id"]

# TODOS los recibos que crea la suite, para borrarlos al final. Antes solo se
# borraba el primero y los otros dos se fugaban en cada corrida: al cabo de las
# corridas había 48 recibos de prueba sobre el CUENTA CORRIENTE del cliente, que
# rompía los mayor y los saldos de las demás suites. Por eso la lista.
RECIBOS = []

st, alicuotas = req("GET", "/api/alicuotas-iva", token=token)
IVA21 = next(a for a in alicuotas if abs(float(a["porcentaje"]) - 21.0) < 0.01)

st, rec = req("POST", "/api/recibos", {
    "cliente_id": CID, "fecha": "2026-10-05", "importe": 25000.00,
    "forma_pago": "transferencia",
}, token)
check("crea el recibo SIN pedir cuenta", st == 201, f"{st} {str(rec)[:130]}")
RID = rec["id"]
RECIBOS.append(RID)
check("y le pegó solo la cuenta fija", rec["cuenta_cobro_id"] == ORIGINAL,
      f"{rec.get('cuenta_cobro_id')} vs {ORIGINAL}")
check("y trae el código y el nombre", rec["cuenta_cobro_codigo"] == fija["codigo"],
      str(rec.get("cuenta_cobro_codigo")))

print("\n== Si el recibo trae la suya, gana la suya ==")
st, rec2 = req("POST", "/api/recibos", {
    "cliente_id": CID, "fecha": "2026-10-06", "importe": 10000.00,
    "forma_pago": "efectivo", "cuenta_cobro_id": CAJA,
}, token)
check("respeta la cuenta del recibo", st == 201
      and rec2["cuenta_cobro_id"] == CAJA,
      f"{st} {rec2.get('cuenta_cobro_id')} vs {CAJA}")
# Este DELETE va EN EL MEDIO a propósito: el Mayor que se mide más abajo tiene
# que ver solo la venta y una cobranza. Si rec2 queda vivo, el mayor muestra
# cuatro movimientos en vez de dos y la prueba mide mal. Igual queda en RECIBOS
# por si el borrado falla con 409 (el recibo tiene asiento y la API no lo deja
# borrar): `_borrar_recibos` lo resuelve por SQL al final.
req("DELETE", f"/api/recibos/{rec2['id']}", token)
RECIBOS.append(rec2["id"])

print("\n== Cambiar la fija no toca los recibos viejos ==")
st, r = req("PUT", "/api/ejercicios/cuenta-cobro-fija", {"id_cuenta": CAJA}, token)
check("cambia la fija a Caja", st == 200 and r["id_cuenta"] == CAJA, f"{st}")
st, rec3 = req("POST", "/api/recibos", {
    "cliente_id": CID, "fecha": "2026-10-07", "importe": 5000.00,
    "forma_pago": "efectivo",
}, token)
check("el recibo nuevo usa la nueva", rec3.get("cuenta_cobro_id") == CAJA,
      str(rec3.get("cuenta_cobro_id")))
st, viejo = req("GET", f"/api/recibos/{RID}", token=token)
check("el recibo viejo sigue con la que tenía",
      viejo["cuenta_cobro_id"] == ORIGINAL,
      f"{viejo['cuenta_cobro_id']} vs {ORIGINAL}")
req("DELETE", f"/api/recibos/{rec3['id']}", token)
RECIBOS.append(rec3["id"])

# Se vuelve al Banco
req("PUT", "/api/ejercicios/cuenta-cobro-fija", {"id_cuenta": BANCO}, token)

print("\n== Factura + recibo = asiento, y el mayor general ==")
st, f = req("POST", "/api/facturas", {
    "cliente_id": CID, "fecha": "2026-10-05", "tipo_comprobante": "factura_a",
    "punto_venta": "9955", "numero": "00000001", "concepto": "Prueba mayor",
    "importe": 121000.00, "condicion_venta": "cta_corriente_30",
    "alicuota_iva_id": IVA21["id"],
}, token)
check("crea la factura con asiento", st == 201 and f.get("id_asiento"),
      f"{st} {str(f)[:120]}")
FID = f["id"]
req("POST", f"/api/recibos/{RID}/aplicaciones",
    {"factura_id": FID, "importe": 25000.00}, token)

db = SessionLocal()
from app.services import asiento_automatico  # noqa: E402

r = asiento_automatico.asiento_de_cobranza(db, RID)
db.close()
check("el recibo genera el asiento de cobranza", r["generado"] is True, str(r)[:120])

DOC_COBRAR = IDS["1.1.03.02"]
st, m = req("GET", f"/api/mayores/{DOC_COBRAR}", token=token)
check("abre el mayor de Documentos a cobrar", st == 200, f"{st}")
check("el mayor es de esa cuenta", m["cuenta"]["codigo"] == "1.1.03.02",
      str(m["cuenta"]))
check("Documentos a cobrar es DEUDORA (es del Activo)",
      m["cuenta"]["deudora_acreadora"] == "DEUDORA",
      str(m["cuenta"]["deudora_acreadora"]))
check("tiene 2 movimientos (la venta y la cobranza)", m["movimientos"] == 2,
      str(m["movimientos"]))
print("     movimientos:")
for l in m["lineas"]:
    print(f"       {l['fecha']}  {l['numero_comprobante'] or '-':<10} "
          f"debe={l['debe']} haber={l['haber']} saldo={l['saldo']}")

# La venta: debe 121.000. Como la cuenta es DEUDORA el saldo va por Debe - Haber.
vta = m["lineas"][0]
check("la venta va al DEBE por 121.000", Decimal(str(vta["debe"])) == Decimal("121000.0000"),
      str(vta["debe"]))
check("deudora: el saldo arranca en +121.000",
      Decimal(str(vta["saldo"])) == Decimal("121000.0000"), str(vta["saldo"]))

cob = m["lineas"][1]
check("la cobranza va al HABER por 25.000",
      Decimal(str(cob["haber"])) == Decimal("25000.0000"), str(cob["haber"]))
check("el saldo baja a +96.000",
      Decimal(str(cob["saldo"])) == Decimal("96000.0000"), str(cob["saldo"]))
check("trae el auxiliar CLIENTE en la cobranza",
      cob["tipo_auxiliar"] == "CLIENTE" and cob["id_auxiliar"] == CID,
      str(cob["tipo_auxiliar"]))
check("el total debe = 121.000",
      Decimal(str(m["total_debe"])) == Decimal("121000.0000"), str(m["total_debe"]))
check("el saldo final es +96.000",
      Decimal(str(m["saldo_final"])) == Decimal("96000.0000"),
      str(m["saldo_final"]))
check("y CIERRA (el acumulado coincide con el total)", m["cierra"] is True,
      str(m))

print("\n== El mayor de una cuenta de detalle (no agrupador) ==")
st, m2 = req("GET", f"/api/mayores/{IDS['2.1.03.01']}", token=token)
check("abre el mayor de IVA a pagar", st == 200, f"{st}")
check("IVA a pagar es ACREEDORA (es un Pasivo)",
      m2["cuenta"]["deudora_acreadora"] == "ACREEDORA",
      str(m2["cuenta"]["deudora_acreadora"]))
check("tiene 1 movimiento (la venta)", m2["movimientos"] == 1,
      str(m2["movimientos"]))
check("acreedora: 21.000 a favor",
      Decimal(str(m2["saldo_final"])) == Decimal("21000.0000"),
      str(m2["saldo_final"]))

print("\n== Filtro por fechas ==")
st, m3 = req("GET", f"/api/mayores/{DOC_COBRAR}?desde=2026-01-01&hasta=2026-09-30",
             token=token)
check("filtrando hasta septiembre no entra la venta (es de octubre)",
      m3["movimientos"] == 0, str(m3["movimientos"]))

st, cg = req("GET", "/api/control-general", token=token)
check("el control general sigue ok", cg["ok"] is True, str(cg["problemas"])[:200])

# ------------------------------------------------------------------ limpieza
# Los recibos de la suite se van por SQL con el asiento primero (ver
# `_borrar_recibos`): por API no se pueden borrar porque tienen asiento.
_db = SessionLocal()
borrados = _borrar_recibos(_db, RECIBOS)
_limpiar(_db)
_db.close()
print(f"     (se borraron {borrados} recibos de prueba)")
# Se deja la cuenta fija como estaba.
req("PUT", "/api/ejercicios/cuenta-cobro-fija", {"id_cuenta": ORIGINAL}, token)

print(f"\n{ok} OK / {len(fallos)} fallos")
if fallos:
    raise SystemExit(1)