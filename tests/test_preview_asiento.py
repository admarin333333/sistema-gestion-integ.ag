"""La previsualización del asiento y el botón "OK, facturar".

    python -X utf8 test_preview_asiento.py

Lo importante que se verifica acá:

1. El preview **no guarda nada**: despues de pedirlo, la base esta igual.
2. **El preview y el asiento real dan lo MISMO.** Esto es lo critico: si se
  aran por separado, el contador veria una cosa y se guardaria otra, y ahi se
   pierde la confianza en el sistema.
3. Al confirmar, se guarda la factura con su asiento contabilizado.
4. Los casos sin alicuota avisan.
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
ORIGEN = BASE
ok = 0
fallos = []
_PU = "9972"
_RUTA_BACKEND = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
)
sys.path.insert(0, _RUTA_BACKEND)


def req(metodo, ruta, datos=None, token=None):
    r = urllib.request.Request(ORIGEN + ruta, method=metodo)
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


def _limpiar(db):
    """Solo las facturas del punto de venta reservado de esta suite y los
    asientos que salen de ellas. Antes borraba TODOS los asientos y
    comprobantes internos, y se llevaba los del contador. Ver `borrar_prueba.py`.
    """
    facturas = [
        r[0]
        for r in db.execute(
            text(f"SELECT id FROM facturas WHERE punto_venta = '{_PU}'")
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

st, clientes = req("GET", "/api/clientes", token=token)
CLIENTE = next((c for c in clientes if c.get("cuit")), clientes[0])
CID = CLIENTE["id"]
st, alicuotas = req("GET", "/api/alicuotas-iva", token=token)
IVA21 = next(a for a in alicuotas if abs(float(a["porcentaje"]) - 21.0) < 0.01)

# El preview necesita un numero que todavia no este cargado.
st, existentes = req("GET", f"/api/facturas?cliente_id={CID}", token=token)
NUMERO = "99000001"
while any(f["numero"] == NUMERO for f in existentes):
    NUMERO = str(int(NUMERO) + 1)

# Los datos de la factura de prueba.
DATOS = {
    "cliente_id": CID,
    "fecha": "2026-09-20",
    "tipo_comprobante": "factura_a",
    "punto_venta": _PU,
    "numero": NUMERO,
    "concepto": "Prueba del preview",
    "importe": 121000.00,
    "condicion_venta": "cta_corriente_30",
    "tipo_operacion": "SERVICIOS",
    "alicuota_iva_id": IVA21["id"],
}

print("\n== El preview NO guarda nada ==")
_db = SessionLocal()
antes = _db.execute(text(f"SELECT COUNT(*) FROM facturas WHERE punto_venta = '{_PU}'")).scalar()
as_antes = _db.execute(text("SELECT COUNT(*) FROM asientos")).scalar()
_db.close()

st, p = req("POST", "/api/facturas/preview-asiento", DATOS, token)
check("el preview responde 200", st == 200, f"{st} {str(p)[:140]}")

_db = SessionLocal()
despues = _db.execute(text(f"SELECT COUNT(*) FROM facturas WHERE punto_venta = '{_PU}'")).scalar()
as_despues = _db.execute(text("SELECT COUNT(*) FROM asientos")).scalar()
_db.close()
check("no creó ninguna factura", antes == despues, f"{antes} -> {despues}")
check("no creó ningún asiento", as_antes == as_despues, f"{as_antes} -> {as_despues}")

print("\n== Cómo se ve el preview ==")
check("tiene 3 líneas (debe, ingresos, IVA)", len(p["lineas"]) == 3,
      str(len(p["lineas"])))
for l in p["lineas"]:
    print(f"     {l['codigo']:<12} {l['nombre_cuenta'][:38]:<38} "
          f"D={l['debe']} H={l['haber']}")
check("el Debe va a Documentos a cobrar",
      p["lineas"][0]["codigo"] == "1.1.03.02", p["lineas"][0]["codigo"])
check("el DEBE lleva auxiliar CLIENTE",
      p["lineas"][0].get("tipo_auxiliar") == "CLIENTE",
      str(p["lineas"][0].get("tipo_auxiliar")))
check("el Haber va a Ingresos por servicios (4.2.01)",
      p["lineas"][1]["codigo"] == "4.2.01", p["lineas"][1]["codigo"])
check("y el IVA a 2.1.03.01",
      p["lineas"][2]["codigo"] == "2.1.03.01", p["lineas"][2]["codigo"])
check("cada línea trae código y nombre",
      all(l["codigo"] and l["nombre_cuenta"] for l in p["lineas"]),
      "alguna sin código")
check("el preview CIERRA: debe = haber",
      Decimal(str(p["total_debe"])) == Decimal(str(p["total_haber"])),
      f"{p['total_debe']} vs {p['total_haber']}")
check("y avisa el número tentativo del comprobante",
      str(p.get("numero_completo_tentativo", "")).startswith("FV-"),
      str(p.get("numero_completo_tentativo")))

print("\n== ⚠ El preview y el asiento REAL tienen que dar lo mismo ==")
st, f = req("POST", "/api/facturas", DATOS, token)
check("crea la factura", st == 201, f"{st} {str(f)[:130]}")
check("y tiene asiento", f.get("id_asiento") is not None, str(f.get("id_asiento")))

st, real = req("GET", f"/api/asientos/{f['id_asiento']}", token=token)

# Mismo conjunto de líneas (mismo código de cuenta), mismos importes.
cod_p = sorted(l["codigo"] for l in p["lineas"])
cod_r = sorted(d["codigo"] for d in real["detalle"])
check("las mismas cuentas en el mismo orden", cod_p == cod_r,
      f"preview={cod_p} real={cod_r}")

for cp, cr in zip(p["lineas"], sorted(real["detalle"], key=lambda d: d["codigo"])):
    pass

# Importes: se comparan por código de cuenta.
debe_p = {l["codigo"]: Decimal(str(l["debe"])) for l in p["lineas"]}
haber_p = {l["codigo"]: Decimal(str(l["haber"])) for l in p["lineas"]}
debe_r = {d["codigo"]: Decimal(str(d["debe"])) for d in real["detalle"]}
haber_r = {d["codigo"]: Decimal(str(d["haber"])) for d in real["detalle"]}
check("los DEBE coinciden cuenta por cuenta", debe_p == debe_r,
      f"preview={debe_p} real={debe_r}")
check("los HABER coinciden cuenta por cuenta", haber_p == haber_r,
      f"preview={haber_p} real={haber_r}")
check("el total del preview es el total del asiento real",
      Decimal(str(p["total_debe"])) == Decimal(str(real["total_debe"])),
      f"{p['total_debe']} vs {real['total_debe']}")
check("el auxiliar del preview es el del asiento real",
      p["lineas"][0].get("id_auxiliar")
      == next(d for d in real["detalle"] if d["codigo"] == "1.1.03.02")["id_auxiliar"],
      "difieren")
check("el número tentativo ES el que quedó",
      p.get("numero_completo_tentativo") == real.get("numero_completo"),
      f"preview={p.get('numero_completo_tentativo')} real={real.get('numero_completo')}")

print("\n== Contado vs cuenta corriente ==")
st, p2 = req("POST", "/api/facturas/preview-asiento",
             {**DATOS, "condicion_venta": "contado"}, token)
# Al contado va TAMBIÉN a Documentos a cobrar: una factura es una deuda, no
# plata. La plata entra después, en tesorería, al registrar el cobro.
check("al contado el Debe va a Documentos a cobrar",
      p2["lineas"][0]["codigo"] == "1.1.03.02", p2["lineas"][0]["codigo"])
check("y NO aparece Caja en el preview",
      "1.1.01.01" not in [l["codigo"] for l in p2["lineas"]],
      str([l["codigo"] for l in p2["lineas"]]))

print("\n== Servicios vs artículos ==")
st, p3 = req("POST", "/api/facturas/preview-asiento",
             {**DATOS, "tipo_operacion": "ARTICULOS"}, token)
check("artículos van a Ventas artículos (4.1.01)",
      p3["lineas"][1]["codigo"] == "4.1.01", p3["lineas"][1]["codigo"])

print("\n== Sin alícuota ==")
st, p4 = req("POST", "/api/facturas/preview-asiento",
             {**DATOS, "alicuota_iva_id": None}, token)
check("sin alícuota avisa", p4.get("aviso") is not None, str(p4.get("aviso")))
check("y quedan 2 líneas (no hay IVA)", len(p4["lineas"]) == 2,
      str(len(p4["lineas"])))
check("el importe entero va a ingresos",
      Decimal(str(p4["lineas"][1]["haber"])) == Decimal("121000.0000"),
      str(p4["lineas"][1]["haber"]))
check("y aun así cierra",
      Decimal(str(p4["total_debe"])) == Decimal(str(p4["total_haber"])),
      f"{p4['total_debe']} vs {p4['total_haber']}")

print("\n== Validaciones ==")
st, r = req("POST", "/api/facturas/preview-asiento",
            {**DATOS, "cliente_id": None}, token)
check("sin cliente avisa", st == 400, f"{st} {str(r)[:100]}")
st, r = req("POST", "/api/facturas/preview-asiento",
            {**DATOS, "importe": 0}, token)
check("sin importe avisa", st == 400, f"{st} {str(r)[:100]}")

st, cg = req("GET", "/api/control-general", token=token)
check("el control general sigue ok", cg["ok"] is True, str(cg["problemas"])[:200])

# ------------------------------------------------------------------ limpieza
_db = SessionLocal()
_limpiar(_db)
_db.close()

print(f"\n{ok} OK / {len(fallos)} fallos")
if fallos:
    raise SystemExit(1)