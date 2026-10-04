# Prueba de la nueva arquitectura: personas + clientes + proveedores
import json
import urllib.request
import urllib.error
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
            texto = resp.read().decode()
            return resp.status, json.loads(texto) if texto else None
    except urllib.error.HTTPError as e:
        texto = e.read().decode() or "{}"
        try:
            return e.code, json.loads(texto)
        except json.JSONDecodeError:
            return e.code, {"detalle": texto}


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

# 1. Listar clientes: solo tipo=cliente, con nro_cuenta
st, clientes = req("GET", "/api/clientes", token=token)
check("lista clientes", st == 200, str(st))
if st == 200:
    check("clientes no vacios", len(clientes) > 0, str(len(clientes)))
    check("todos tipo=cliente", all(c.get("tipo") == "cliente" for c in clientes),
          str([c.get("tipo") for c in clientes]))
    check("todos con nro_cuenta", all(c.get("nro_cuenta") for c in clientes),
          str([c.get("nro_cuenta") for c in clientes]))

# 2. Listar proveedores: solo tipo=proveedor
st, proveedores = req("GET", "/api/proveedores", token=token)
check("lista proveedores", st == 200, str(st))
if st == 200:
    check("todos tipo=proveedor", all(p.get("tipo") == "proveedor" for p in proveedores),
          str([p.get("tipo") for p in proveedores]))
    check("proveedores con nro_cuenta", all(p.get("nro_cuenta") for p in proveedores),
          str([p.get("nro_cuenta") for p in proveedores]))

# 3. Los correlativos son independientes por módulo
st, clientes = req("GET", "/api/clientes", token=token)
st2, proveedores = req("GET", "/api/proveedores", token=token)
if st == 200 and st2 == 200 and clientes and proveedores:
    check("correlativo independiente (cliente 1 y proveedor 1 coexisten)",
          any(c["nro_cuenta"] == 1 for c in clientes) and any(p["nro_cuenta"] == 1 for p in proveedores),
          f"cli={[c['nro_cuenta'] for c in clientes]} prov={[p['nro_cuenta'] for p in proveedores]}")

# 4. Búsqueda de clientes no trae proveedores
st, busqueda = req("GET", "/api/clientes?q=PROVEEDOR", token=token)
check("busqueda clientes", st == 200, str(st))
if st == 200:
    check("busqueda no mezcla", all(c.get("tipo") == "cliente" for c in busqueda),
          str([c.get("tipo") for c in busqueda]))

# 5. Búsqueda de proveedores no trae clientes
st, busqueda = req("GET", "/api/proveedores?q=PROVEEDOR", token=token)
check("busqueda proveedores", st == 200, str(st))
if st == 200:
    check("busqueda proveedor no mezcla", all(p.get("tipo") == "proveedor" for p in busqueda),
          str([p.get("tipo") for p in busqueda]))

# 6. Obtener cliente por id
st, clientes = req("GET", "/api/clientes", token=token)
if st == 200 and clientes:
    cid = clientes[0]["id"]
    st, uno = req("GET", f"/api/clientes/{cid}", token=token)
    check("obtener cliente", st == 200, f"{st} {str(uno)[:120]}")
    if st == 200:
        check("cliente con datos de persona", uno.get("nombre") is not None, str(uno)[:120])
        check("cliente con servicios", "servicios" in uno, str(uno)[:120])

# 7. Obtener proveedor por id
st, proveedores = req("GET", "/api/proveedores", token=token)
if st == 200 and proveedores:
    pid = proveedores[0]["id"]
    st, uno = req("GET", f"/api/proveedores/{pid}", token=token)
    check("obtener proveedor", st == 200, f"{st} {str(uno)[:120]}")

# 8. Crear cliente (body con servicios embebido)
import time
import sys as _sys

_sys.path.insert(0, _RUTA_BACKEND)
from app.schemas.persona import digito_verificador_cuit  # noqa: E402

# El backend valida el dígito verificador del CUIT (módulo 11), así que el
# número hay que armarlo bien: 8 dígitos + el verificador que les corresponde.
sello = str(int(time.time()))[-8:]
_base = f"20{sello}"
_dv = digito_verificador_cuit(_base) or 0
cuit_prueba = f"{_base[:2]}-{_base[2:]}-{_dv}"

st, nuevo = req("POST", "/api/clientes", {
    "tipo_persona": "fisica",
    "nombre": "Test",
    "apellido": "Pueba",
    "cuit": cuit_prueba,
    "dni": sello,
    "actividad_economica": "servicios",
    "tipo_actividad": "autonomo",
    "condicion_iva": "consumidor_final",
    "servicios": [],
}, token=token)
check("crear cliente", st == 201, f"{st} {str(nuevo)[:200]}")
nuevo_cli_id = nuevo.get("id") if st == 201 else None

# 9. Crear proveedor
st, nuevo_prov = req("POST", "/api/proveedores", {
    "tipo_persona": "juridica",
    "nombre": "Proveedor Test",
    "cuit": "30-88888888-4",
    "actividad_economica": "comercio",
    "tipo_actividad": "responsable_inscripto",
    "condicion_iva": "responsable_inscripto",
}, token=token)
check("crear proveedor", st == 201, f"{st} {str(nuevo_prov)[:200]}")
nuevo_prov_id = nuevo_prov.get("id") if st == 201 else None

# 10. CUIT duplicado se rechaza (único global en personas)
st, _ = req("POST", "/api/proveedores", {
    "tipo_persona": "juridica",
    "nombre": "Otro con mismo CUIT",
    "cuit": "30-88888888-4",
    "actividad_economica": "comercio",
    "tipo_actividad": "responsable_inscripto",
    "condicion_iva": "responsable_inscripto",
}, token=token)
check("rechaza CUIT duplicado", st == 409, str(st))

# 11. Modificar cliente
if nuevo_cli_id:
    st, mod = req("PUT", f"/api/clientes/{nuevo_cli_id}", {
        "observaciones": "modificado por la prueba",
        "servicios": [],
    }, token=token)
    check("modificar cliente", st == 200, f"{st} {str(mod)[:150]}")
    if st == 200:
        check("guarda la modificación", mod.get("observaciones") == "modificado por la prueba",
              str(mod.get("observaciones")))

# 12. Borrar los creados (limpieza)
if nuevo_prov_id:
    st, _ = req("DELETE", f"/api/proveedores/{nuevo_prov_id}", token=token)
    check("borrar proveedor de prueba", st == 204, str(st))
if nuevo_cli_id:
    st, _ = req("DELETE", f"/api/clientes/{nuevo_cli_id}", token=token)
    check("borrar cliente de prueba", st == 204, str(st))

print(f"\n{ok} OK / {len(fallos)} fallos")
if fallos:
    raise SystemExit(1)