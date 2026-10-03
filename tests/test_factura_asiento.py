"""Prueba del asiento que se genera solo al cargar la factura.

    python -X utf8 test_factura_asiento.py

Cubre las cuatro cosas que se pidieron:
  1. El asiento se genera SOLO al dar de alta la factura.
  2. Tiene fecha, codigo de cuenta, nombre de cuenta, debe y haber.
  3. Total del Debe = total del Haber, y si no cierra NO se contabiliza.
  4. Los botones Generar / Modificar / Anular, y que anular la factura
     NO anula el asiento.
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
_RUTA_BACKEND = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
)
sys.path.insert(0, _RUTA_BACKEND)

PV = "9971"


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


def d(x):
    return Decimal(str(x))


st, tok = req("POST", "/api/auth/login", {"usuario": "admin", "password": "admin123"})
token = tok.get("access_token")
check("login", st == 200 and token, str(st))

from sqlalchemy import text  # noqa: E402
from app.database import SessionLocal  # noqa: E402
import borrar_prueba  # noqa: E402

_db = SessionLocal()


def limpiar():
    """Borra lo que dejaron corridas anteriores. El orden lo manda el FK.

    SOLO lo de prueba: las facturas del punto de venta reservado de esta suite
    (`PV`), y los asientos quevenues de ellas. Las tres líneas que había antes
    (`DELETE FROM asientos`, etc. a secas) borraban los asientos reales del
    contador en cada corrida. Ver `borrar_prueba.py`.
    """
    facturas = [
        r[0]
        for r in _db.execute(
            text(f"SELECT id FROM facturas WHERE punto_venta = '{PV}'")
        ).all()
    ]
    borrar_prueba.limpiar_asientos(_db, facturas)
    borrar_prueba.limpiar_comprobantes(_db)
    if facturas:
        marcas = ",".join(str(i) for i in facturas)
        _db.execute(text(f"DELETE FROM facturas WHERE id IN ({marcas})"))
    _db.commit()


limpiar()
_db.close()

st, clientes = req("GET", "/api/clientes", token=token)
CLIENTE = next((c for c in clientes if c.get("cuit")), clientes[0])
CID = CLIENTE["id"]
print(f"     cliente: {CLIENTE['nombre_completo']}")

st, alicuotas = req("GET", "/api/alicuotas-iva", token=token)
IVA21 = next(a for a in alicuotas if abs(float(a["porcentaje"]) - 21.0) < 0.01)


def nueva(numero, **extra):
    cuerpo = {
        "cliente_id": CID,
        "fecha": "2026-11-05",
        "tipo_comprobante": "factura_a",
        "punto_venta": PV,
        "numero": numero,
        "concepto": "Prueba asiento automatico",
        "importe": 121000.00,
        "condicion_venta": "cta_corriente_30",
    }
    cuerpo.update(extra)
    return req("POST", "/api/facturas", cuerpo, token)


print("\n== El IVA lo desglosa el backend ==")
st, f = nueva("00000001", alicuota_iva_id=IVA21["id"], tipo_operacion="SERVICIOS")
check("crea la factura", st == 201, f"{st} {str(f)[:130]}")
check("neto = 100.000,00", d(f["neto"]) == Decimal("100000.00"), str(f.get("neto")))
check("iva = 21.000,00", d(f["iva"]) == Decimal("21000.00"), str(f.get("iva")))
check("importe = neto + iva (al centavo)",
      d(f["neto"]) + d(f["iva"]) == d(f["importe"]),
      f"{f['neto']} + {f['iva']} != {f['importe']}")
check("guarda la alícuota aplicada 21,00",
      d(f["alicuota_iva_aplicada"]) == Decimal("21.00"),
      str(f.get("alicuota_iva_aplicada")))
check("guarda el tipo de operación", f["tipo_operacion"] == "SERVICIOS",
      str(f.get("tipo_operacion")))
fid = f["id"]

print("\n== Sin alícuota: todo es neto, IVA en cero ==")
st, f2 = nueva("00000002", importe=50000.00)
check("crea la factura sin alícuota", st == 201, f"{st} {str(f2)[:120]}")
check("neto = importe entero", d(f2["neto"]) == Decimal("50000.00"),
      str(f2.get("neto")))
check("iva = 0,00", d(f2["iva"]) == Decimal("0.00"), str(f2.get("iva")))

print("\n== Alícuota inexistente ==")
st, r = nueva("00000003", alicuota_iva_id=9999)
check("rechaza la alícuota que no existe", st == 400, f"{st} {str(r)[:120]}")

print("\n== El asiento se generó SOLO al dar de alta ==")
check("la factura trae id_asiento", f.get("id_asiento") is not None,
      f"id_asiento={f.get('id_asiento')}")
check("y el comprobante FV-", str(f.get("numero_comprobante_asiento", "")).startswith("FV-"),
      str(f.get("numero_comprobante_asiento")))
check("el estado del asiento es CONTABILIZADO",
      f.get("estado_asiento") == "CONTABILIZADO", str(f.get("estado_asiento")))

print("\n== Cómo se ve el asiento: fecha, cuenta, debe, haber ==")
st, a = req("GET", f"/api/asientos/{f['id_asiento']}", token=token)
check("tiene fecha", a["fecha"] == "2026-11-05", str(a.get("fecha")))
check("tiene número de comprobante", str(a["numero_completo"]).startswith("FV-"),
      str(a.get("numero_completo")))
check("tiene 3 líneas (debe, ingresos, iva)", len(a["detalle"]) == 3,
      str(len(a["detalle"])))
for linea in a["detalle"]:
    tiene = bool(linea["codigo"]) and bool(linea["nombre_cuenta"])
    check(f"línea con código y nombre: {linea['codigo']}", tiene,
          f"{linea['codigo']} / {linea['nombre_cuenta']}")
    check(f"  la línea tiene debe o haber",
          d(linea["debe"]) > 0 or d(linea["haber"]) > 0,
          f"debe={linea['debe']} haber={linea['haber']}")

print("\n== Partida doble: Debe = Haber ==")
check("total del debe = 121.000", d(a["total_debe"]) == Decimal("121000.0000"),
      str(a["total_debe"]))
check("total del haber = 121.000", d(a["total_haber"]) == Decimal("121000.0000"),
      str(a["total_haber"]))
check("debe = haber", a["balanceado"] is True, str(a["diferencia"]))
check("diferencia en cero", d(a["diferencia"]) == 0, str(a["diferencia"]))
debe = sum(d(l["debe"]) for l in a["detalle"])
haber = sum(d(l["haber"]) for l in a["detalle"])
check("sumando las líneas también da igual", debe == haber, f"{debe} vs {haber}")

print("\n== Botón GENERAR (de nuevo) ==")
st, r = req("POST", f"/api/facturas/{fid}/asiento", token=token)
check("no genera dos veces", st == 409, f"{st} {str(r)[:130]}")
check("y lo explica", "ya tiene el asiento" in str(r.get("detail", "")).lower(),
      str(r.get("detail")))

print("\n== Botón MODIFICAR ==")
st, plan = req("GET", "/api/plan-cuentas", token=token)
ids = {c["codigo"]: c["id_cuenta"] for c in plan}
st, r = req("PUT", f"/api/facturas/{fid}/asiento", {"detalle": [
    {"id_cuenta": ids["1.1.03.02"], "debe": 121000, "haber": 0,
     "tipo_auxiliar": "CLIENTE", "id_auxiliar": CID},
    {"id_cuenta": ids["4.2.01"], "debe": 0, "haber": 100000},
    {"id_cuenta": ids["2.1.03.01"], "debe": 0, "haber": 21000},
]}, token)
check("acepta las líneas nuevas", st == 200, f"{st} {str(r)[:130]}")
check("vuelve a CONTABILIZADO solo", r.get("estado") == "CONTABILIZADO",
      str(r.get("estado")))
check("y sigue cerrado", d(r["total_debe"]) == d(r["total_haber"]),
      f"{r.get('total_debe')} vs {r.get('total_haber')}")

print("\n== Si el asiento NO cierra, no contabiliza ==")
st, r = req("PUT", f"/api/facturas/{fid}/asiento", {"detalle": [
    {"id_cuenta": ids["1.1.03.02"], "debe": 121000, "haber": 0},
    {"id_cuenta": ids["4.2.01"], "debe": 0, "haber": 100000},
]}, token)
check("rechaza", st == 400, f"{st} {str(r)[:130]}")
check("dice cuánto falta", "21000" in str(r.get("detail", "")).replace(".", ""),
      str(r.get("detail"))[:160])
st, a2 = req("GET", f"/api/asientos/{f['id_asiento']}", token=token)
check("el asiento queda en BORRADOR", a2["estado"] == "BORRADOR", a2["estado"])
check("y NO entra en los saldos", d(a2["total_debe"]) != d(a2["total_haber"]),
      f"{a2['total_debe']} vs {a2['total_haber']}")

# Se deja como estaba, para seguir probando
req("PUT", f"/api/facturas/{fid}/asiento", {"detalle": [
    {"id_cuenta": ids["1.1.03.02"], "debe": 121000, "haber": 0,
     "tipo_auxiliar": "CLIENTE", "id_auxiliar": CID},
    {"id_cuenta": ids["4.2.01"], "debe": 0, "haber": 100000},
    {"id_cuenta": ids["2.1.03.01"], "debe": 0, "haber": 21000},
]}, token)

print("\n== Botón ANULAR ASIENTO ==")
st, r = req("POST", f"/api/facturas/{fid}/asiento/anular", token=token)
check("anula el asiento", st == 200, f"{st} {str(r)[:130]}")
check("el asiento queda ANULADO", r.get("estado_asiento") == "ANULADO",
      str(r.get("estado_asiento")))
check("la factura sigue como estaba (no la anula)", r.get("estado") != "anulada",
      str(r.get("estado")))
check("y sigue teniendo el mismo asiento", r.get("id_asiento") == f["id_asiento"],
      f"{r.get('id_asiento')} vs {f['id_asiento']}")

st, r = req("PUT", f"/api/facturas/{fid}/asiento", {"detalle": [
    {"id_cuenta": ids["1.1.03.02"], "debe": 1, "haber": 0},
]}, token)
check("un asiento anulado no se modifica más", st == 409, f"{st} {str(r)[:130]}")
st, r = req("POST", f"/api/facturas/{fid}/asiento", token=token)
check("ni se puede volver a generar sobre el mismo", st == 409, f"{st}")

print("\n== Anular la FACTURA no toca el asiento ==")
st, f3 = nueva("00000004", importe=30000.00)
aid3 = f3.get("id_asiento")
check("la factura nueva tiene su asiento", aid3 is not None, str(aid3))
st, r = req("POST", f"/api/facturas/{f3['id']}/anular", token=token)
check("anula la factura", st == 200, f"{st}")
check("la factura queda ANULADA", r["estado"] == "anulada", r.get("estado"))
check("pero el asiento sigue CONTABILIZADO",
      r.get("estado_asiento") == "CONTABILIZADO",
      str(r.get("estado_asiento")))

st, cg = req("GET", "/api/control-general", token=token)
check("el control general sigue ok", cg["ok"] is True, str(cg.get("problemas"))[:200])

# ------------------------------------------------------------------ limpieza
_db = SessionLocal()
limpiar()
_db.close()

print(f"\n{ok} OK / {len(fallos)} fallos")
if fallos:
    raise SystemExit(1)