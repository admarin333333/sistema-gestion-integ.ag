# Prueba del endpoint de recálculo en vivo de los cuadros
import os
import sys
import json
import urllib.request
import urllib.error
# La dirección de la API sale de `GC_BASE_URL` para poder correr estas pruebas
# contra la base de PRUEBAS y no contra la del estudio. Si la variable no
# está, usa 8010 como antes: no cambia cómo se corren.

BASE = os.environ.get("GC_BASE_URL", "http://127.0.0.1:8010")

# Esta suite necesita el ejercicio RT54 número 1: recalcula y compara los totales
# antes y después, así que sin un balance cargado no hay con qué comparar. Está
# en la base del estudio y no en la de pruebas. Si falta, se avisa y se omite la
# suite en vez de reventar con un `KeyError: 'cabecera'`.
# Ver `datos_de_prueba.py`.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from datos_de_prueba import chequear_o_salir  # noqa: E402
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
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


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

chequear_o_salir("recalculo", token, BASE)

# Limpia las celdas del ejercicio 1 (las del prueba anterior) para medir limpio
st, ej0 = req("GET", "/api/balance-rt54/ejercicios/1", token=token)
st, _ = req("PUT", "/api/balance-rt54/ejercicios/1", {
    "cabecera": ej0["cabecera"], "valores": [], "celdas_nota": [],
}, token)
check("limpieza", st == 200, str(st))

# Recalcula con dos importes de la 2.1 y una previsión negativa de la 2.3
st, r = req("POST", "/api/balance-rt54/cuadros-notas", {
    "celdas_nota": [
        {"clave": "2.1:20:C", "valor": 100},
        {"clave": "2.1:21:C", "valor": 50.25},
        {"clave": "2.3:44:C", "valor": 10},
        {"clave": "2.3:45:C", "valor": 20},
        {"clave": "2.3:50:C", "valor": -5},
    ],
}, token)
check("POST 200", st == 200, str(st) + str(r)[:200])
check("devuelve las19 notas", len(r) == 19 and "2.1" in r and "3.4" in r, str(len(r)))

f21 = {f["fila"]: f for f in r["2.1"]["filas"]}
check("2.1 Total C = 150.25", f21[24]["celdas"]["C"]["valor"] == 150.25, str(f21[24]["celdas"]["C"]))
check("2.1 Total D = 0", f21[24]["celdas"]["D"]["valor"] == 0)
check("2.1 dato sin cargar = null", f21[22]["celdas"]["C"]["valor"] is None)
f23 = {f["fila"]: f for f in r["2.3"]["filas"]}
check("2.3 Subtotal C = 30", f23[49]["celdas"]["C"]["valor"] == 30, str(f23[49]["celdas"]["C"]))
check("2.3 Total C = 25 (30 - 5)", f23[51]["celdas"]["C"]["valor"] == 25, str(f23[51]["celdas"]["C"]))

# No guarda nada: otro pedido vacío da todo en0/null
st, r2 = req("POST", "/api/balance-rt54/cuadros-notas", {"celdas_nota": []}, token)
check("vacío 200", st == 200, str(st))
f21b = {f["fila"]: f for f in r2["2.1"]["filas"]}
check("vacío: Total C = 0", f21b[24]["celdas"]["C"]["valor"] == 0, str(f21b[24]["celdas"]["C"]))
check("vacío: dato = null", f21b[20]["celdas"]["C"]["valor"] is None)

# Clave inválida -> 400
st, r3 = req("POST", "/api/balance-rt54/cuadros-notas", {
    "celdas_nota": [{"clave": "2.1:99:C", "valor": 1}],
}, token)
check("clave inválida -> 400", st == 400, str(st))

# La base NO cambió: el ejercicio sigue sin celdas guardadas
st, ej = req("GET", "/api/balance-rt54/ejercicios/1", token=token)
f21c = {f["fila"]: f for f in [n for n in ej["notas"] if n["clave"] == "2.1"][0]["cuadro"]["filas"]}
check("GET sigue en0 (no guardó)", f21c[24]["celdas"]["C"]["valor"] == 0, str(f21c[24]["celdas"]["C"]))

print()
print(f"RESULTADO: {ok} OK, {len(fallos)} fallos")
for f in fallos:
    print("  -", f)
