"""Prueba de los asientos automáticos: factura -> asiento, recibo -> asiento.

    python -X utf8 test_asientos_automaticos.py

Desde el 02/10/2026 el asiento de la factura sale **solo al darla de alta**
(`factura_service.crear` llama a `asiento_automatico.asiento_de_venta`). Esta
suite prueba ese camino de verdad, no llamando al service a mano.

Qué cuenta va en cada lado NO está escrito acá: sale de `config_asientos`,
que es una tabla editable.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from decimal import Decimal

BASE = "http://127.0.0.1:8010"
ok = 0
fallos = []
creados = {"facturas": [], "asientos": [], "comprobantes": []}
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
            return e.code, {"detalle": t}


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
from app.database import SessionLocal  # noqa: E402
import borrar_prueba  # noqa: E402


def _limpiar(db):
    """Borra lo que dejó una corrida anterior. El orden lo manda el FK:
    `asiento_origen` y `aplicaciones_recibo` apuntan a facturas con RESTRICT.

    SOLO las facturas de prueba (las de punto de venta reservado y las que
    dicen "PRUEBA" en el concepto). Antes esta suite hacía `DELETE FROM
    asientos` a secas y se llevaba los asientos reales del contador en cada
    corrida; como después mide diferencias contra una línea de base, el borrado
    no se notaba nunca. Ver `borrar_prueba.py`.
    """
    borrar_prueba.limpiar_todo(db)


_db = SessionLocal()
_limpiar(_db)
_db.close()

st, clientes = req("GET", "/api/clientes", token=token)
CLIENTE = next((c for c in clientes if c.get("cuit")), clientes[0])
CLIENTE_ID = CLIENTE["id"]
check("hay un cliente con CUIT", CLIENTE.get("cuit") is not None, str(CLIENTE)[:100])
print(f"     cliente de prueba: {CLIENTE['nombre_completo']}")

st, alicuotas = req("GET", "/api/alicuotas-iva", token=token)
IVA21 = next(a for a in alicuotas if abs(float(a["porcentaje"]) - 21.0) < 0.01)
st, plan = req("GET", "/api/plan-cuentas", token=token)
IDS = {c["codigo"]: c["id_cuenta"] for c in plan}


def crear_factura(numero, **extra):
    """Crea la factura con el IVA y el tipo de operación ya cargados.
    El asiento se genera solo, dentro de este POST."""
    cuerpo = {
        "cliente_id": CLIENTE_ID,
        "fecha": "2026-10-10",
        "tipo_comprobante": "factura_a",
        "punto_venta": "9900",
        "numero": numero,
        "concepto": "Prueba automatica",
        "importe": 121000.00,
        "condicion_venta": "cta_corriente_30",
    }
    cuerpo.update(extra)
    return req("POST", "/api/facturas", cuerpo, token)


print("\n== Factura de SERVICIOS con IVA 21% ==")
# 121.000 con 21% -> neto 100.000,00 / iva 21.000,00
NETO = Decimal("100000.00")
IVA = Decimal("21000.00")
TOTAL = Decimal("121000.00")

st, f = crear_factura("990001", alicuota_iva_id=IVA21["id"],
                      tipo_operacion="SERVICIOS")
check("crea la factura", st == 201, f"{st} {str(f)[:130]}")
fid = f["id"]
creados["facturas"].append(fid)
check("el backend desglosa el IVA: neto", Decimal(str(f["neto"])) == NETO,
      str(f.get("neto")))
check("el backend desglosa el IVA: iva", Decimal(str(f["iva"])) == IVA,
      str(f.get("iva")))
check("neto + iva = importe, al centavo",
      Decimal(str(f["neto"])) + Decimal(str(f["iva"])) == TOTAL,
      f"{f['neto']} + {f['iva']}")

print("\n== El asiento sale SOLO al dar de alta ==")
check("la factura trae id_asiento", f.get("id_asiento") is not None,
      f"id_asiento={f.get('id_asiento')}")
check("con el código de factura (FV-)",
      str(f.get("numero_comprobante_asiento", "")).startswith("FV-"),
      str(f.get("numero_comprobante_asiento")))
check("y queda CONTABILIZADO", f.get("estado_asiento") == "CONTABILIZADO",
      str(f.get("estado_asiento")))
aid = f["id_asiento"]
creados["asientos"].append(aid)

st, a = req("GET", f"/api/asientos/{aid}", token=token)
check("3 líneas: debe, ingresos, IVA", len(a["detalle"]) == 3, str(len(a["detalle"])))
check("DEBE = 121.000", Decimal(str(a["detalle"][0]["debe"])) == TOTAL,
      str(a["detalle"][0]["debe"]))
check("el DEBE va a Documentos a cobrar (1.1.03.02)",
      a["detalle"][0]["codigo"] == "1.1.03.02", a["detalle"][0]["codigo"])
check("el DEBE lleva auxiliar CLIENTE",
      a["detalle"][0]["tipo_auxiliar"] == "CLIENTE"
      and a["detalle"][0]["id_auxiliar"] == CLIENTE_ID,
      str(a["detalle"][0]["tipo_auxiliar"]))
ing = next(d for d in a["detalle"] if d["codigo"] == "4.2.01")
check("HABER ingresos por servicios = neto", Decimal(str(ing["haber"])) == NETO,
      str(ing["haber"]))
iva = next(d for d in a["detalle"] if d["codigo"] == "2.1.03.01")
check("HABER IVA a pagar = 21.000", Decimal(str(iva["haber"])) == IVA, str(iva["haber"]))
check("partida doble: debe = haber",
      Decimal(str(a["total_debe"])) == Decimal(str(a["total_haber"])),
      f"{a['total_debe']} vs {a['total_haber']}")
check("contabilizado (sale de fábrica, sin pasos)", a["estado"] == "CONTABILIZADO",
      a["estado"])

print("\n== No se asienta dos veces ==")
st, r = req("POST", f"/api/facturas/{fid}/asiento", token=token)
check("el botón Generar no duplica", st == 409, f"{st} {str(r)[:130]}")

print("\n== Factura de ARTÍCULOS ==")
st, f2 = crear_factura("990002", alicuota_iva_id=IVA21["id"],
                       tipo_operacion="ARTICULOS")
fid2 = f2["id"]
creados["facturas"].append(fid2)
st, a2 = req("GET", f"/api/asientos/{f2['id_asiento']}", token=token)
codigos = [d["codigo"] for d in a2["detalle"]]
check("el Haber va a Ventas artículos (4.1.01)", "4.1.01" in codigos, str(codigos))
check("NO va a Ingresos por servicios", "4.2.01" not in codigos, str(codigos))

print("\n== Factura al CONTADO ==")
st, f3 = crear_factura("990003", importe=21000.00,
                       condicion_venta="contado",
                       alicuota_iva_id=IVA21["id"])
fid3 = f3["id"]
creados["facturas"].append(fid3)
st, a3 = req("GET", f"/api/asientos/{f3['id_asiento']}", token=token)
# Al contado va TAMBIÉN a Documentos a cobrar, NO a Caja: una factura es una
# deuda del cliente, no plata recibida. La plata entra después, en tesorería,
# cuando se registra el cobro (ahí el Haber es Documentos y el Debe el banco).
check("al contado el DEBE va a Documentos a cobrar (1.1.03.02)",
      a3["detalle"][0]["codigo"] == "1.1.03.02", a3["detalle"][0]["codigo"])
check("y NO toca Caja", "1.1.01.01" not in [d["codigo"] for d in a3["detalle"]],
      str([d["codigo"] for d in a3["detalle"]]))

print("\n== Factura SIN alícuota ==")
st, f6 = crear_factura("990004", importe=50000.00)
fid6 = f6["id"]
creados["facturas"].append(fid6)
check("neto = importe entero", Decimal(str(f6["neto"])) == Decimal("50000.00"),
      str(f6.get("neto")))
check("iva = 0,00", Decimal(str(f6["iva"])) == Decimal("0.00"), str(f6.get("iva")))
st, a7 = req("GET", f"/api/asientos/{f6['id_asiento']}", token=token)
check("el asiento igual sale (2 líneas)", len(a7["detalle"]) == 2,
      str(len(a7["detalle"])))
check("sin línea de IVA",
      all(d["codigo"] != "2.1.03.01" for d in a7["detalle"]),
      str([d["codigo"] for d in a7["detalle"]]))

print("\n== Factura anulada ==")
st, _ = req("POST", f"/api/facturas/{fid3}/anular", token=token)
db = SessionLocal()
from app.services import asiento_automatico  # noqa: E402

try:
    r = asiento_automatico.asiento_de_venta(db, fid3)
    check("una factura anulada no genera asiento nuevo", False,
          f"generó: {r}")
except Exception as e:
    check("una factura anulada no genera asiento nuevo", "anulada" in str(e).lower(),
          str(e)[:120])
db.close()

print("\n== Recibo: la cobranza ==")
st, rec = req("POST", "/api/recibos", {
    "cliente_id": CLIENTE_ID, "fecha": "2026-10-20", "importe": 50000.00,
    "forma_pago": "transferencia",
}, token)
check("crea el recibo", st == 201, f"{st} {str(rec)[:130]}")
rid = rec["id"]
# Desde el 02/10/2026 el recibo toma SOLO la cuenta de cobro fija de
# Configuración: no hay que elegirla al cargar. Por eso ya sale con la cuenta
# puesta y el asiento sale sin preguntar nada.
check("el recibo ya trae la cuenta de cobro (la fija de Configuración)",
      rec.get("cuenta_cobro_id") is not None, str(rec.get("cuenta_cobro_id")))
check("y trae el código y el nombre de la cuenta",
      rec.get("cuenta_cobro_codigo") is not None,
      str(rec.get("cuenta_cobro_codigo")))

st, ap = req("POST", f"/api/recibos/{rid}/aplicaciones",
             {"factura_id": fid, "importe": 50000.00}, token)
check("lo aplica a la factura", st == 201, f"{st} {str(ap)[:130]}")

db = SessionLocal()
r5 = asiento_automatico.asiento_de_cobranza(db, rid)
db.close()
check("genera el asiento de cobranza", r5["generado"] is True, str(r5)[:150])
check("con el código de recibo (RC-)",
      str(r5["numero_completo"]).startswith("RC-"), str(r5.get("numero_completo")))
creados["asientos"].append(r5["asiento_id"])

st, a5 = req("GET", f"/api/asientos/{r5['asiento_id']}", token=token)
check("2 líneas: banco y documentos a cobrar", len(a5["detalle"]) == 2,
      str(len(a5["detalle"])))
# El DEBE va a la cuenta que entró la plata: la que trae el recibo (la fija).
check("el DEBE va a la cuenta del recibo (la fija de Configuración)",
      a5["detalle"][0]["codigo"] == rec["cuenta_cobro_codigo"],
      f"asiento={a5['detalle'][0]['codigo']} recibo={rec['cuenta_cobro_codigo']}")
check("el DEBE es 50.000",
      Decimal(str(a5["detalle"][0]["debe"])) == Decimal("50000.00"),
      str(a5["detalle"][0]["debe"]))
check("el HABER va a Documentos a cobrar (1.1.03.02)",
      a5["detalle"][1]["codigo"] == "1.1.03.02", a5["detalle"][1]["codigo"])
check("el HABER lleva auxiliar CLIENTE",
      a5["detalle"][1]["tipo_auxiliar"] == "CLIENTE", str(a5["detalle"][1]["tipo_auxiliar"]))
check("cierra", a5["balanceado"] is True, str(a5["diferencia"]))
# Cada código numera por su cuenta: FV-000001 y RC-000001 son distintos.
check("factura y recibo con CÓDIGO distinto",
      str(r5["numero_completo"]).split("-")[0] != "FV",
      str(r5.get("numero_completo")))

db = SessionLocal()
r6 = asiento_automatico.asiento_de_cobranza(db, rid)
db.close()
check("el recibo tampoco se asienta dos veces", r6["generado"] is False, str(r6))

print("\n== Saldos ==")
st, saldos = req("GET", "/api/saldos?con_movimientos=true", token=token)
con_iva = next((s for s in saldos if s["codigo"] == "2.1.03.01"), None)
check("la cuenta de IVA tiene movimientos", con_iva is not None
      and con_iva["movimientos"] > 0, str(con_iva)[:120])
check("IVA a pagar es acreedor y da positivo",
      con_iva and Decimal(str(con_iva["saldo"])) > 0, str(con_iva)[:120])

st, cg = req("GET", "/api/control-general", token=token)
check("el control general sigue ok", cg["ok"] is True, str(cg["problemas"])[:200])

# ------------------------------------------------------------------ limpieza
db = SessionLocal()
_limpiar(db)
# Este recibo se lo guarda la suite, así que lo borra apuntando a su id. Pero
# tiene que irse su asiento primero: `asiento_origen` apunta al recibo con
# RESTRICT, y con `DELETE FROM recibos` a secas MySQL corta la suite con
# "Cannot delete or update a parent row".
for (aid,) in db.execute(
    text("SELECT id_asiento FROM asiento_origen WHERE id_recibo = :r"), {"r": rid}
).all():
    db.execute(text("DELETE FROM asiento_origen WHERE id_asiento = :a"), {"a": aid})
    db.execute(text("DELETE FROM asiento_detalle WHERE id_asiento = :a"), {"a": aid})
    db.execute(text("DELETE FROM asientos WHERE id_asiento = :a"), {"a": aid})
db.execute(text("DELETE FROM aplicaciones_recibo WHERE recibo_id = :r"), {"r": rid})
db.execute(text("DELETE FROM recibo_pagos WHERE recibo_id = :r"), {"r": rid})
db.execute(text(f"DELETE FROM recibos WHERE id = {rid}"))

# Y los recibos que dejaron corridas anteriores. El borrado de arriba va solo
# por id: si una corrida se muerde después de crear el recibo y antes de
# borrarlo, el recibo queda con su asiento en la base y contamina el Mayor de
# documentos a cobrar de las suites que corren después (pasó: quedaron 2
# asientos de 50.000 del 20/10/2026 durante semanas). Acá se limpian por la
# firma de esta suite: mismo importe y misma fecha.
for (r_fuera,) in db.execute(
    text(
        "SELECT DISTINCT id FROM recibos "
        "WHERE importe = 50000.00 AND fecha = '2026-10-20' AND id <> :r"
    ),
    {"r": rid},
).all():
    for (aid,) in db.execute(
        text("SELECT id_asiento FROM asiento_origen WHERE id_recibo = :r"),
        {"r": r_fuera},
    ).all():
        db.execute(text("DELETE FROM asiento_origen WHERE id_asiento = :a"), {"a": aid})
        db.execute(text("DELETE FROM asiento_detalle WHERE id_asiento = :a"), {"a": aid})
        db.execute(text("DELETE FROM asientos WHERE id_asiento = :a"), {"a": aid})
    db.execute(
        text("DELETE FROM aplicaciones_recibo WHERE recibo_id = :r"), {"r": r_fuera}
    )
    db.execute(text("DELETE FROM recibo_pagos WHERE recibo_id = :r"), {"r": r_fuera})
    db.execute(text("DELETE FROM recibos WHERE id = :r"), {"r": r_fuera})

db.commit()
db.close()

print(f"\n{ok} OK / {len(fallos)} fallos")
if fallos:
    raise SystemExit(1)