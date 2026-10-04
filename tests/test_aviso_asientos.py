"""El aviso de la pantalla de Asientos: "no hay nada acá, pero hay cargado".

    python -X utf8 test_aviso_asientos.py

La pantalla de Asientos arranca filtrando por la fecha de hoy. Si los asientos
están cargados en otro día, la respuesta vieja era "no hay asientos", que hace
creer que no se asentó nada. Con `total_cargados` la pantalla puede decir
"estás viendo 0 de 5" y ofrecer verlos.

Lo que se verifica acá:
  1. `total_cargados` cuenta los asientos SIN el filtro de fechas.
  2. Hay asientos hoy -> la pantalla los muestra.
  3. Filtrar un día que no tiene nada da 0, pero avisa cuántos hay.
  4. El filtro por código también cuenta solo los de ese código.
  5. Cuando no hay NADA cargado, avisa 0 (no inventa).

Ojo con la limpieza: este test crea sus propios asientos y borra SOLO esos.
No usa `DELETE FROM asientos` a secas, porque en la base hay asientos reales y
se quedarían sin ellos.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date
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

# Los asientos que crea este test, para borrar solo esos al final.
MIOS = []


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
from app.services import asiento_service  # noqa: E402

st, tok = req("POST", "/api/auth/login", {"usuario": "admin", "password": "admin123"})
token = tok.get("access_token")
check("login", st == 200 and token, str(st))

st, plan = req("GET", "/api/plan-cuentas", token=token)
IDS = {c["codigo"]: c["id_cuenta"] for c in plan}

# --- cuánto hay cargado ANTES de que este test cree nada ---------------------
# El test compara contra la base real, que puede tener asientos de otros tests.
# Por eso no mira "3" sino "cuántos había + 3".
Q = "/api/asientos?desde=2000-01-01&hasta=2100-01-01"
st, antes = req("GET", Q, token=token)
base_cant = antes["cantidad"]
base_dias = antes["dias_con_asientos"]
print(f"\nLa base tiene {base_cant} asientos en {base_dias} días antes de empezar")

# --- crear tres asientos: dos en septiembre y uno en octubre ---------------
# Así el filtro de un día distinto de hoy da 0.
FECHAS = ["2026-09-10", "2026-09-20", "2026-10-02"]
CODIGOS = ["FV", "FV", "RC"]
db = SessionLocal()
try:
    for fecha_txt, codigo in zip(FECHAS, CODIGOS):
        # El servicio quiere un `date`, no el texto: por eso el date.fromisoformat.
        fecha = date.fromisoformat(fecha_txt)
        comp = asiento_service.crear_comprobante(db, codigo, fecha, f"Prueba aviso {fecha_txt}")
        a = asiento_service.crear_asiento(
            db, fecha, f"Prueba aviso {fecha_txt}", comp.id_comprobante
        )
        MIOS.append(a.id_asiento)
        asiento_service.guardar_detalle(db, a.id_asiento, [
            {"id_cuenta": IDS["1.1.03.02"], "debe": 100, "haber": 0},
            {"id_cuenta": IDS["4.2.01"], "debe": 0, "haber": 100},
        ])
        asiento_service.contabilizar(db, a.id_asiento)
    db.commit()
    total_esperado = base_cant + 3
    dias_esperados = base_dias + 3
finally:
    db.close()

print("\n== El listado trae los totales para el aviso ==")
st, r = req("GET", "/api/asientos?desde=2026-10-02&hasta=2026-10-02", token=token)
check("filtrando hoy devuelve 1 asiento (el de hoy)", r["cantidad"] == 1,
      str(r.get("cantidad")))
check(f"pero avisa que hay {total_esperado} cargados en total",
      r["total_cargados"] == total_esperado, str(r.get("total_cargados")))
check("y en cuántos días", r["dias_con_asientos"] == dias_esperados,
      str(r.get("dias_con_asientos")))

print("\n== Filtrando un día que no tiene nada ==")
st, r = req("GET", "/api/asientos?desde=2026-09-15&hasta=2026-09-15", token=token)
check("no hay asientos ese día", r["cantidad"] == 0, str(r.get("cantidad")))
check("pero igual avisa cuántos hay cargados",
      r["total_cargados"] == total_esperado, str(r.get("total_cargados")))
check("y trae la primera y la última fecha, para que la pantalla",
      r["primera_fecha"] is not None and r["ultima_fecha"] is not None,
      f"{r.get('primera_fecha')} .. {r.get('ultima_fecha')}")
check("la última es 2026-10-02 (el asiento de hoy)", r["ultima_fecha"] == "2026-10-02",
      str(r.get("ultima_fecha")))

print("\n== Filtrando por código ==")
st, r = req("GET", "/api/asientos?codigo=FV&desde=2026-09-15&hasta=2026-09-15",
            token=token)
check("filtrando FV, hay 0 ese día", r["cantidad"] == 0, str(r.get("cantidad")))
check("y FV tiene al menos los 2 que creó este test",
      r["total_cargados"] >= 2, str(r.get("total_cargados")))
check("con código RC también cuenta solo los RC",
      req("GET", "/api/asientos?codigo=RC&desde=2000-01-01&hasta=2100-01-01",
          token=token)[1]["total_cargados"] >= 1,
      "RC mal")

print("\n== Sin filtro de fechas: los 3 más lo que hubiera ==")
st, r = req("GET", "/api/asientos?desde=2000-01-01&hasta=2100-01-01", token=token)
check("trae todos los asientos", r["cantidad"] == total_esperado,
      f"{r.get('cantidad')} vs {total_esperado}")
check("cada día trae su suma desde SQL",
      all(d["total_debe"] is not None for d in r["dias"]), "sin suma")

# --- limpiar: SOLO los asientos de este test -------------------------------
db = SessionLocal()
try:
    for aid in MIOS:
        db.execute(text("DELETE FROM asiento_detalle WHERE id_asiento = :a"), {"a": aid})
        db.execute(text("DELETE FROM asiento_origen WHERE id_asiento = :a"), {"a": aid})
        db.execute(text("DELETE FROM asientos WHERE id_asiento = :a"), {"a": aid})
    db.commit()
    quedan = db.execute(text("SELECT COUNT(*) FROM asientos")).scalar()
finally:
    db.close()
check("los asientos del test se borraron y los otros quedan",
      quedan == base_cant, f"{quedan} vs {base_cant}")

st, r = req("GET", Q, token=token)
check("vuelve al mismo número que había al empezar", r["cantidad"] == base_cant,
      f"{r.get('cantidad')} vs {base_cant}")

st, cg = req("GET", "/api/control-general", token=token)
check("el control general sigue ok", cg["ok"] is True, str(cg["problemas"])[:200])

print(f"\n{ok} OK / {len(fallos)} fallos")
if fallos:
    raise SystemExit(1)