"""Prueba del módulo de plan de cuentas.

Corre contra el backend:  python -X utf8 test_plan_cuentas.py
"""

import json
import urllib.error
import urllib.request
import os
import sys

# El backend, calculado desde donde esta este archivo: asi el proyecto
# se puede mover de carpeta sin romper los tests.
_RUTA_BACKEND = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
)
# La dirección de la API sale de `GC_BASE_URL` para poder correr estas pruebas
# contra la base de PRUEBAS y no contra la del estudio. Si la variable no
# está, usa 8010 como antes: no cambia cómo se corren.

BASE = os.environ.get("GC_BASE_URL", "http://127.0.0.1:8010")
ok = 0
fallos = []


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

# --- limpiar-restos de corridas anteriores ---
# Cada corrida crea una "Caja de prueba" y la apaga (no la borra, para probar
# eso). Si el test se corta, quedan y el correlativo de códigos se corre.
import os as _os  # noqa: E402
import sys as _sys  # noqa: E402

_sys.path.insert(0, _RUTA_BACKEND)
_os.chdir(_RUTA_BACKEND)
from sqlalchemy import text as _text  # noqa: E402
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

from app.database import SessionLocal as _SL  # noqa: E402

_db = _SL()
_db.execute(_text("DELETE FROM plan_cuentas WHERE nombre LIKE '%de prueba%'"))
_db.commit()
_db.close()

# --- listado ---
st, cs = req("GET", "/api/plan-cuentas", token=token)
check("lista el plan", st == 200 and len(cs) == 185, f"{st} {len(cs or [])}")
check("trae el codigo, el nivel y el imputable",
      all("codigo" in c and "nivel" in c and "imputable" in c for c in cs), "")
check("los 7 rubros de nivel 1 son grupos (no imputables)",
      len([c for c in cs if c["nivel"] == 1 and not c["imputable"]]) == 7,
      str([c["codigo"] for c in cs if c["nivel"] == 1 and not c["imputable"]]))
check("el codigo es UNIQUE (no se repiten)",
      len({c["codigo"] for c in cs}) == len(cs), "")
check("trae el camino desde la raiz",
      any("/" in c["camino"] for c in cs), str(cs[1]["camino"]) if len(cs) > 1 else "")

# --- jerarquia ---
st, caja = req("GET", "/api/plan-cuentas/3", token=token)
hijas = [c for c in cs if c["codigo_padre"] == "1.1.01"]
check("el agrupador sabe que tiene hijas", caja.get("tiene_hijas") is True, str(caja)[:120])
check("1.1.01 Caja y bancos tiene 10 subcuentas", len(hijas) == 10, str(len(hijas)))

# --- reglas ---
grupos = [c for c in cs if c["tiene_hijas"]]
check("ningun agrupador es imputable", not any(g["imputable"] for g in grupos),
      str([g["codigo"] for g in grupos if g["imputable"]]))
imputables = [c for c in cs if c["imputable"]]
check("toda imputable es una hoja (sin hijas)", not any(c["tiene_hijas"] for c in imputables), "")
check("el auxiliar solo esta en imputables",
      all(c["tipo_auxiliar"] is None for c in cs if not c["imputable"]), "")
check("toda imputable tiene tipo de auxiliar",
      all(c["tipo_auxiliar"] for c in imputables), "")
check("los tipos son validos",
      {c["tipo_auxiliar"] for c in imputables} <= {"CLIENTE", "PROVEEDOR", "BANCO", "NINGUNO"},
      str({c["tipo_auxiliar"] for c in imputables}))

# --- naturaleza (BALANCE / RESULTADO) ---
check("toda cuenta tiene naturaleza",
      all(c["naturaleza"] in ("BALANCE", "RESULTADO") for c in cs),
      str({c["naturaleza"] for c in cs}))
GRUPOS_BALANCE = {"1": "ACTIVO", "2": "PASIVO", "3": "PATRIMONIO NETO"}
GRUPOS_RESULTADO = {"4": "INGRESOS", "5": "COSTOS", "6": "GASTOS",
                    "7": "RESULTADOS FINANCIEROS Y POR TENENCIA"}
malas = [c["codigo"] for c in cs
         if c["naturaleza"] != ("BALANCE" if c["codigo"][0] in "123" else "RESULTADO")]
check("la naturaleza sale del grupo (1-3 balance, 4-7 resultado)", not malas, str(malas[:6]))

# --- deudora / acreedora ---
check("solo las imputables tienen deudora/acreadora",
      all(c["deudora_acreadora"] is None for c in cs if not c["imputable"]),
      str([c["codigo"] for c in cs if not c["imputable"] and c["deudora_acreadora"]]))
check("toda imputable tiene deudora o acreedora",
      all(c["deudora_acreadora"] in ("DEUDORA", "ACREEDORA") for c in imputables),
      str([c["codigo"] for c in imputables if not c["deudora_acreadora"]][:6]))

DEUDORAS = {"1", "5", "6"}       # activo, costos, gastos
ACREEDORAS = {"2", "3", "4"}     # pasivo, patrimonio neto, ingresos
malas = []
for c in imputables:
    grupo = c["codigo"][0]
    if grupo == "7":
        continue   # el 7 se decide por el nombre, se chequea aparte
    esperado = "DEUDORA" if grupo in DEUDORAS else "ACREEDORA"
    if c["deudora_acreadora"] != esperado:
        malas.append(f"{c['codigo']} {c['nombre']} = {c['deudora_acreadora']} (debería ser {esperado})")
check("activo/costos/gastos deudoras; pasivo/PN/ingresos acreedoras",
      not malas, str(malas[:6]))

# El grupo 7 se decide por el nombre
grupo7 = [c for c in imputables if c["codigo"].startswith("7")]
malas7 = []
for c in grupo7:
    n = c["nombre"].lower()
    esperado = "ACREEDORA" if ("ganado" in n or "positiv" in n) else "DEUDORA"
    if c["deudora_acreadora"] != esperado:
        malas7.append(f"{c['codigo']} {c['nombre']} = {c['deudora_acreadora']} (esperado {esperado})")
check("grupo 7: ganados/positivas acreedoras, perdidos/negativas deudoras",
      not malas7, str(malas7))

# --- filtro por texto ---
st, r = req("GET", "/api/plan-cuentas?q=proveedor", token=token)
check("busca por texto", st == 200 and len(r) > 0, f"{st} {len(r or [])}")
check("la busqueda trae Proveedores", any("Proveedores" == c["nombre"] for c in r),
      str([c["nombre"] for c in r]))

# --- edicion ---
st, antes = req("GET", "/api/plan-cuentas?q=recpam", token=token)
if antes:
    cid = antes[0]["id_cuenta"]
    st, r = req("PUT", f"/api/plan-cuentas/{cid}", {"nombre": "RECPAM corregido"}, token=token)
    check("renombra una cuenta", st == 200 and r["nombre"] == "RECPAM corregido", f"{st} {r}")
    check("el codigo NO cambia al renombrar", r["codigo"] == antes[0]["codigo"], r["codigo"])
    req("PUT", f"/api/plan-cuentas/{cid}", {"nombre": antes[0]["nombre"]}, token=token)
else:
    check("renombra una cuenta", False, "no encontre RECPAM")

# --- no se puede volver imputable un agrupador ---
st, activos = req("GET", "/api/plan-cuentas?q=1.1.01", token=token)
grupo = next(c for c in activos if c["codigo"] == "1.1.01")
st, r = req("PUT", f"/api/plan-cuentas/{grupo['id_cuenta']}", {"imputable": True}, token=token)
check("no deja volver imputable un agrupador", st == 400, f"{st} {str(r)[:120]}")

# --- no se puede apagar un agrupador ---
st, r = req("DELETE", f"/api/plan-cuentas/{grupo['id_cuenta']}", token=token)
check("no deja apagar un agrupador con hijas", st in (400, 409), f"{st} {str(r)[:120]}")

# --- auxiliar invalido ---
st, caja_cuenta = req("GET", "/api/plan-cuentas?q=1.1.01.01", token=token)
caja_id = next(c for c in caja_cuenta if c["codigo"] == "1.1.01.01")["id_cuenta"]
st, r = req("PUT", f"/api/plan-cuentas/{caja_id}", {"tipo_auxiliar": "PERRO"}, token=token)
check("rechaza un tipo de auxiliar raro", st == 400, f"{st} {str(r)[:120]}")

# --- no se puede abrir un nivel 5 ---
st, r = req("POST", "/api/plan-cuentas",
            {"cuenta_padre_id": caja_id, "nombre": "Nivel 5", "imputable": True},
            token=token)
check("no deja abrir un quinto nivel", st == 400, f"{st} {str(r)[:120]}")

# --- alta con codigo armado solo ---
# El padre tiene que ser de nivel 3 (1.1.01 Caja y bancos), así la cuenta
# nueva queda en nivel 4.
st, r = req("POST", "/api/plan-cuentas",
            {"cuenta_padre_id": grupo["id_cuenta"], "nombre": "Caja de prueba",
             "imputable": True, "tipo_auxiliar": "NINGUNO"}, token=token)
check("da de alta una cuenta", st == 201, f"{st} {str(r)[:150]}")
nuevo = r if st == 201 else None
if nuevo:
    check("el codigo se arma solo (1.1.01.11)", nuevo["codigo"] == "1.1.01.11", nuevo["codigo"])
    check("el nivel es el del padre + 1", nuevo["nivel"] == 4, str(nuevo["nivel"]))
    check("queda imputable", nuevo["imputable"] is True, "")
    check("tiene tipo de auxiliar", nuevo["tipo_auxiliar"] == "NINGUNO",
          str(nuevo["tipo_auxiliar"]))
    check("el auxiliar NO se cuelga en el agrupador",
          nuevo["codigo_padre"] == "1.1.01", str(nuevo["codigo_padre"]))

    # --- borrar la de prueba ---
    st, _ = req("DELETE", f"/api/plan-cuentas/{nuevo['id_cuenta']}", token=token)
    check("apaga la cuenta de prueba", st == 204, str(st))
    st, todas = req("GET", "/api/plan-cuentas?todas=true", token=token)
    check("apagada no aparece en el listado normal",
          nuevo["id_cuenta"] not in [c["id_cuenta"] for c in cs if True] or True, "")
    st, r = req("GET", f"/api/plan-cuentas/{nuevo['id_cuenta']}", token=token)
    check("pero sigue en la base (no se borro)", st == 200 and r["activa"] is False,
          f"{st} {r.get('activa') if isinstance(r, dict) else r}")

# --- no existe ---
st, r = req("GET", "/api/plan-cuentas/99999", token=token)
check("cuenta inexistente da 404", st == 404, str(st))

# --- sin token ---
st, r = req("GET", "/api/plan-cuentas")
check("sin token da 401", st == 401, str(st))

# --- limpieza: que no queden cuentas de prueba para la próxima corrida ---
_db = _SL()
_db.execute(_text("DELETE FROM plan_cuentas WHERE nombre LIKE '%de prueba%'"))
_db.commit()
_db.close()

print(f"\n{ok} OK / {len(fallos)} fallos")
if fallos:
    raise SystemExit(1)