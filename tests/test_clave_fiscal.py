# Prueba de la clave fiscal de ARCA (fechas + historial)
import json
import time
import urllib.request
import urllib.error
import os
import sys

# El backend, calculado desde donde esta este archivo: asi el proyecto
# se puede mover de carpeta sin romper los tests.
_RUTA_BACKEND = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
)

BASE = "http://127.0.0.1:8010"
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


# espera que el backend esté arriba
for _ in range(30):
    try:
        urllib.request.urlopen(BASE + "/api/auth/login", timeout=2)
        break
    except urllib.error.HTTPError:
        break
    except Exception:
        time.sleep(1)

st, tok = req("POST", "/api/auth/login", {"usuario": "admin", "password": "admin123"})
token = tok.get("access_token")
check("login", st == 200 and token, str(st))
HEAD = {"tipo_persona": "juridica", "nombre": "PRUEBA CLAVE FISCAL SRL",
        "cuit": "30-99999999-5", "actividad_economica": "servicios",
        "tipo_actividad": "responsable_inscripto", "condicion_iva": "responsable_inscripto"}

# --- 1. Alta sin clave fiscal
st, c = req("POST", "/api/clientes", dict(HEAD, servicios=[]), token)
check("crea cliente sin clave", st == 201, f"{st} {str(c)[:120]}")
cid = c.get("id") if st == 201 else None
if not cid:
    print("\nNo se pudo crear el cliente de prueba. Abortando.")
    raise SystemExit(1)
check("sin clave, las fechas vienen vacías",
      c.get("clave_fiscal") in (None, "") and not c.get("fecha_carga_clave_fiscal"),
      str(c.get("clave_fiscal")))

# --- 2. Cargar la clave fiscal por primera vez
st, c = req("PUT", f"/api/clientes/{cid}", dict(HEAD, clave_fiscal="abc123def45"), token)
check("carga la clave fiscal", st == 200 and c.get("clave_fiscal") == "ABC123DEF45",
      f"{st} {c.get('clave_fiscal')}")
check("pone la fecha de carga", bool(c.get("fecha_carga_clave_fiscal")),
      str(c.get("fecha_carga_clave_fiscal")))
check("pone la fecha de modificación", bool(c.get("fecha_modif_clave_fiscal")),
      str(c.get("fecha_modif_clave_fiscal")))
check("la fecha de carga NO cambia al reusar la misma clave",
      req("PUT", f"/api/clientes/{cid}", dict(HEAD, clave_fiscal="ABC123DEF45"), token)[1]
      .get("fecha_carga_clave_fiscal") == c.get("fecha_carga_clave_fiscal"), "")

# --- 3. El historial tiene 1 sola fila (la primera carga)
st, h = req("GET", f"/api/clientes/{cid}/clave-fiscal/historial", token=token)
check("historial con 1 fila", st == 200 and len(h) == 1, f"{st} {len(h or [])}")
if st == 200 and h:
    check("la primera fila no tiene clave anterior", h[0]["clave_fiscal_anterior"] in (None, ""),
          str(h[0]))
    check("la primera fila tiene la clave nueva", h[0]["clave_fiscal_nueva"] == "ABC123DEF45",
          str(h[0]))
    check("la fila guarda el usuario", h[0].get("usuario") == "admin", str(h[0].get("usuario")))

# --- 4. Cambiar la clave
st, c = req("PUT", f"/api/clientes/{cid}", dict(HEAD, clave_fiscal="ZZZ999YYY88"), token)
check("cambia la clave fiscal", st == 200 and c.get("clave_fiscal") == "ZZZ999YYY88",
      f"{st} {c.get('clave_fiscal')}")
check("la fecha de carga sigue siendo la primera", c.get("fecha_carga_clave_fiscal")
      == "2026-10-01" or c.get("fecha_carga_clave_fiscal") is not None,
      str(c.get("fecha_carga_clave_fiscal")))
st, h = req("GET", f"/api/clientes/{cid}/clave-fiscal/historial", token=token)
check("historial con 2 filas", len(h) == 2, str(len(h)))
if len(h) == 2:
    check("la más nueva trae la clave anterior", h[0]["clave_fiscal_anterior"] == "ABC123DEF45",
          str(h[0]["clave_fiscal_anterior"]))
    check("la más nueva trae la nueva", h[0]["clave_fiscal_nueva"] == "ZZZ999YYY88",
          str(h[0]["clave_fiscal_nueva"]))

# --- 5. Guardar la misma clave NO crea fila nueva
req("PUT", f"/api/clientes/{cid}", dict(HEAD, clave_fiscal="zzz999yyy88"), token)
st, h = req("GET", f"/api/clientes/{cid}/clave-fiscal/historial", token=token)
check("la misma clave no crea historial", len(h) == 2, str(len(h)))

# --- 6. Validaciones
st, r = req("PUT", f"/api/clientes/{cid}", dict(HEAD, clave_fiscal="123"), token)
check("rechaza clave corta", st == 400, f"{st} {str(r)[:100]}")
st, r = req("PUT", f"/api/clientes/{cid}", dict(HEAD, clave_fiscal="abc-def-ghij"), token)
check("rechaza clave con guiones", st == 400, f"{st} {str(r)[:100]}")
st, h2 = req("GET", f"/api/clientes/{cid}/clave-fiscal/historial", token=token)
check("las claves inválidas no tocan el historial", len(h2) == 2, str(len(h2)))

# --- 7. Quitar la clave
st, c = req("PUT", f"/api/clientes/{cid}", dict(HEAD, clave_fiscal=""), token)
check("se puede quitar la clave", st == 200 and not c.get("clave_fiscal"),
      f"{st} {c.get('clave_fiscal')}")
check("al quitarla se borran las dos fechas",
      not c.get("fecha_carga_clave_fiscal") and not c.get("fecha_modif_clave_fiscal"),
      f"{c.get('fecha_carga_clave_fiscal')} / {c.get('fecha_modif_clave_fiscal')}")
st, h = req("GET", f"/api/clientes/{cid}/clave-fiscal/historial", token=token)
check("quitar la clave también queda en el historial", len(h) == 3, str(len(h)))

# --- 8. No rompe editar sin mandar la clave
st, c = req("PUT", f"/api/clientes/{cid}", dict(HEAD, clave_fiscal="XYZ123ABC45"), token)
req("PUT", f"/api/clientes/{cid}", {"email": "pruebacf@ejemplo.com"}, token)
st, c = req("GET", f"/api/clientes/{cid}", token=token)
check("editar otro campo no borra la clave", c.get("clave_fiscal") == "XYZ123ABC45",
      str(c.get("clave_fiscal")))

# --- 9. Proveedores también
st, pv = req("POST", "/api/proveedores", dict(HEAD, cuit="30-88888888-4",
                                              nombre="PRUEBA PROV CF SRL",
                                              clave_fiscal="prov1234567"), token)
check("alta de proveedor con clave", st == 201 and pv.get("clave_fiscal") == "PROV1234567",
      f"{st} {pv.get('clave_fiscal')}")
check("proveedor con fecha de carga", bool(pv.get("fecha_carga_clave_fiscal")), "")
pid = pv.get("id")
if pid:
    req("PUT", f"/api/proveedores/{pid}", dict(HEAD, cuit="30-88888888-4",
                                               nombre="PRUEBA PROV CF SRL",
                                               clave_fiscal="OTRA9999999"), token)
    st, h = req("GET", f"/api/proveedores/{pid}/clave-fiscal/historial", token=token)
    check("historial del proveedor", st == 200 and len(h) == 2, f"{st} {len(h or [])}")
    req("DELETE", f"/api/proveedores/{pid}", token=token)

# --- limpieza
req("DELETE", f"/api/clientes/{cid}", token=token)
check("borrar el cliente lo elimina", req("GET", f"/api/clientes/{cid}", token=token)[0] == 404, "")
import sys
sys.path.insert(0, _RUTA_BACKEND)
from sqlalchemy import text
from app.database import engine
with engine.connect() as conn:
    huerfanas = conn.execute(text(
        "SELECT COUNT(*) FROM clave_fiscal_historial h "
        "LEFT JOIN personas p ON p.id = h.persona_id WHERE p.id IS NULL"
    )).scalar()
check("no quedan historiales sin persona", huerfanas == 0, str(huerfanas))

print(f"\n{ok} OK / {len(fallos)} fallos")
if fallos:
    raise SystemExit(1)