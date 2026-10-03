# Prueba del intervalo contable del balance: años + día/mes de cierre del cliente
import json
import urllib.request
import urllib.error
from datetime import date, timedelta

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


st, tok = req("POST", "/api/auth/login", {"usuario": "admin", "password": "admin123"})
token = tok.get("access_token")
check("login", st == 200 and token, str(st))

# Cliente de prueba: uno que NO sea el 13 (el 13 es RI sin alícuota y no se guarda)
st, clientes = req("GET", "/api/clientes", token=token)
check("hay clientes", st == 200 and len(clientes) > 0, str(st))

# Buscamos uno que acepte PUT (no RI sin alícuota)
candidato = None
for c in clientes:
    if c.get("condicion_iva") != "responsable_inscripto" or c.get("alicuota_iva"):
        candidato = c
        break
check("cliente apto para la prueba", candidato is not None, "ninguno")
cli_id = candidato["id"] if candidato else None


def payload_de(c):
    return {
        "tipo_persona": c["tipo_persona"],
        "nombre": c["nombre"],
        "apellido": c.get("apellido"),
        "cuit": c.get("cuit"),
        "dni": c.get("dni"),
        "email": c.get("email"),
        "cod_area": c.get("cod_area"),
        "telefono": c.get("telefono"),
        "calle": c.get("calle"),
        "numero_calle": c.get("numero_calle"),
        "localidad": c.get("localidad"),
        "codigo_postal": c.get("codigo_postal"),
        "provincia": c.get("provincia"),
        "actividad_economica": c["actividad_economica"],
        "tipo_actividad": c["tipo_actividad"],
        "condicion_iva": c["condicion_iva"],
        "alicuota_iva_id": (c.get("alicuota_iva") or {}).get("id"),
        "observaciones": c.get("observaciones"),
        "fecha_cierre_ejercicio": c.get("fecha_cierre_ejercicio"),
        "servicios": [s["id"] for s in (c.get("servicios") or [])],
    }


cierre_original = candidato.get("fecha_cierre_ejercicio")
p = payload_de(candidato)
# El cliente cierra el 31 de julio (el año del input da igual)
p["fecha_cierre_ejercicio"] = "2020-07-31"
st, _ = req("PUT", f"/api/clientes/{cli_id}", p, token)
check("guarda fecha de cierre 31/07", st == 200, str(st))

# --- Crear el balance con años: 2024 a 2025, cierre 31/07 ---
st, nuevo = req("POST", "/api/balance-rt54/ejercicios", {
    "cliente_id": cli_id,
    "nombre": "prueba-intervalo",
    "fecha_inicio": "2024-01-01",   # se pisa con el intervalo calculado
    "fecha_fin": "2025-01-01",
    "anio_inicio": 2024,
    "anio_fin": 2025,
}, token)
check("crea balance con años", st in (200, 201), f"{st} {str(nuevo)[:200]}")
bal_id = nuevo.get("cabecera", {}).get("id") if st in (200, 201) else None

if bal_id:
    cab = nuevo["cabecera"]
    # Cierre 31/07/2025, inicio = 01/08/2024
    check("fecha_fin = 31/07/2025", cab["fecha_fin"] == "2025-07-31", cab["fecha_fin"])
    check("fecha_inicio = 01/08/2024", cab["fecha_inicio"] == "2024-08-01", cab["fecha_inicio"])
    check("guarda anio_inicio", cab.get("anio_inicio") == 2024, str(cab.get("anio_inicio")))
    check("guarda anio_fin", cab.get("anio_fin") == 2025, str(cab.get("anio_fin")))
    check("guarda dia/mes de cierre (31/7)",
          cab.get("dia_mes_cierre") == 31 and cab.get("mes_cierre") == 7,
          f"{cab.get('dia_mes_cierre')}/{cab.get('mes_cierre')}")

    # --- Un solo año: el ejercicio cierra ese día/mes ---
    st, uno = req("POST", "/api/balance-rt54/ejercicios", {
        "cliente_id": cli_id,
        "nombre": "prueba-un-anio",
        "fecha_inicio": "2025-01-01",
        "fecha_fin": "2025-01-01",
        "anio_inicio": 2025,
        "anio_fin": 2025,
    }, token)
    check("crea balance de un año", st in (200, 201), f"{st} {str(uno)[:150]}")
    if st in (200, 201):
        c2 = uno["cabecera"]
        check("un año: cierra 31/07/2025", c2["fecha_fin"] == "2025-07-31", c2["fecha_fin"])
        req("DELETE", f"/api/balance-rt54/ejercicios/{c2['id']}", token=token)

    # --- Años invertidos: error claro ---
    st, err = req("POST", "/api/balance-rt54/ejercicios", {
        "cliente_id": cli_id,
        "nombre": "prueba-malos-anos",
        "fecha_inicio": "2025-01-01",
        "fecha_fin": "2025-01-01",
        "anio_inicio": 2025,
        "anio_fin": 2024,
    }, token)
    check("rechaza años invertidos", st == 400, f"{st} {str(err)[:120]}")

    # --- 29/02 en año no bisiesto: cae al 28/02 ---
    p2 = payload_de(candidato)
    p2["fecha_cierre_ejercicio"] = "2020-02-29"
    st, _ = req("PUT", f"/api/clientes/{cli_id}", p2, token)
    check("guarda cierre 29/02", st == 200, str(st))
    st, feb = req("POST", "/api/balance-rt54/ejercicios", {
        "cliente_id": cli_id,
        "nombre": "prueba-bisiesto",
        "fecha_inicio": "2025-01-01",
        "fecha_fin": "2025-01-01",
        "anio_inicio": 2025,
        "anio_fin": 2025,
    }, token)
    check("crea balance con cierre 29/02", st in (200, 201), f"{st} {str(feb)[:150]}")
    if st in (200, 201):
        c3 = feb["cabecera"]
        # 2025 no es bisiesto → 28/02/2025
        check("29/02 en anio no bisiesto cae a 28/02/2025",
              c3["fecha_fin"] == "2025-02-28", c3["fecha_fin"])
        req("DELETE", f"/api/balance-rt54/ejercicios/{c3['id']}", token=token)

    # limpieza del balance de prueba
    st, _ = req("DELETE", f"/api/balance-rt54/ejercicios/{bal_id}", token=token)
    check("borra balance de prueba", st == 204, str(st))

# restaura la fecha de cierre del cliente
p3 = payload_de(candidato)
p3["fecha_cierre_ejercicio"] = cierre_original
st, _ = req("PUT", f"/api/clientes/{cli_id}", p3, token)
check("restaura fecha de cierre del cliente", st == 200, str(st))

print(f"\n{ok} OK / {len(fallos)} fallos")
if fallos:
    raise SystemExit(1)