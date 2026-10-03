"""El catálogo de servicios: alta, duplicados y borrado con clientes.

    python -X utf8 test_servicios_api.py

El 02/10/2026 el catálogo era solo de lectura: la API tenía únicamente
`GET /api/servicios`, y para agregar un servicio había que entrar a la base a
mano. Los clientes ya elegían de esta lista al darse de alta, así que un
servicio nuevo no se podía ofrecer a nadie.

Lo que se verifica:
  1. El listado viene ordenado por `orden` (es el orden del formulario).
  2. El alta crea el servicio y lo devuelve.
  3. Sin `orden` explícito va AL FINAL, sin desordenar el resto.
  4. El nombre no se puede repetir, y da un error que se entiende.
  5. Sólo el ADMIN puede crear y borrar (un operador recibe 403).
  6. Un servicio CON clientes no se borra; uno sin clientes sí.
  7. Un servicio nuevo se puede elegir al dar de alta un cliente.
"""

import json
import os
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8010"
ok = 0
fallos = []
_RUTA_BACKEND = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
)
sys.path.insert(0, _RUTA_BACKEND)

# Lo que este test crea, para borrarlo al final.
SERVICIOS = []
CLIENTES = []


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

from app.database import SessionLocal  # noqa: E402

st, tok = req("POST", "/api/auth/login", {"usuario": "admin", "password": "admin123"})
admin = tok.get("access_token")
check("login admin", st == 200 and admin, str(st))

st, tokop = req("POST", "/api/auth/login",
                {"usuario": "operador", "password": "operador123"})
operador = tokop.get("access_token")
check("login operador", st == 200 and operador, str(st))

# =====================================================================
print("\n== 1. El listado viene en orden ==")
st, lista = req("GET", "/api/servicios", token=admin)
check("responde 200", st == 200, f"{st} {str(lista)[:120]}")
check("trae servicios", len(lista) > 0, str(len(lista)))
ordenes = [s["orden"] for s in lista]
check("están ordenados por `orden` (no es el orden de id)",
      ordenes == sorted(ordenes), str(ordenes))
check("cada uno trae id, nombre y orden",
      all({"id", "nombre", "orden"} <= set(s) for s in lista),
      str(lista[0]) if lista else "")
print(f"      {len(lista)} servicios: {', '.join(s['nombre'][:22] for s in lista[:4])}…")

# =====================================================================
print("\n== 2. El alta ==")
NOMBRE = "Prueba catálogo servicio"
st, nuevo = req("POST", "/api/servicios", {"nombre": NOMBRE}, token=admin)
check("crea el servicio -> 201", st == 201, f"{st} {str(nuevo)[:150]}")
check("devuelve el nombre", nuevo and nuevo.get("nombre") == NOMBRE, str(nuevo))
check("devuelve el id", nuevo and nuevo.get("id"), str(nuevo))
if nuevo and nuevo.get("id"):
    SERVICIOS.append(nuevo["id"])

st, r = req("GET", f"/api/servicios/{nuevo['id']}", token=admin)
check("se puede traer por id", st == 200 and r.get("nombre") == NOMBRE,
      f"{st} {str(r)[:100]}")

st, r = req("GET", "/api/servicios/999999", token=admin)
check("servicio inexistente -> 404", st == 404, str(st))

# =====================================================================
print("\n== 3. Sin orden va AL FINAL, sin desordenar ==")
# Ojo: no se mira el `orden` exacto (depende de cuántas veces corrió el test),
# sino que el nuevo quedó después del último que había.
check("el nuevo quedó al final",
      nuevo["orden"] > ordenes[-1],
      f"{nuevo['orden']} vs último previo {ordenes[-1]}")
st, lista2 = req("GET", "/api/servicios", token=admin)
check("y el listado sigue ordenado",
      [s["orden"] for s in lista2] == sorted(s["orden"] for s in lista2),
      str([s["orden"] for s in lista2]))
check("el nuevo es el último de la lista",
      lista2[-1]["id"] == nuevo["id"], str(lista2[-1]["nombre"]))

# =====================================================================
print("\n== 4. El nombre no se puede repetir ==")
st, r = req("POST", "/api/servicios", {"nombre": NOMBRE}, token=admin)
check("repite el mismo nombre -> 409", st == 409, f"{st} {str(r)[:150]}")
st, r = req("POST", "/api/servicios", {"nombre": NOMBRE.upper()}, token=admin)
check("repite en MAYÚSCULAS -> 409 (comparación sin distinguir caja)", st == 409,
      f"{st} {str(r)[:150]}")
check("y el error dice cuál es, sin jerga de base de datos",
      st == 409 and "Ya existe" in str(r.get("detail", "")),
      str(r.get("detail")))

st, r = req("POST", "/api/servicios", {"nombre": "   "}, token=admin)
check("nombre en blanco -> 422", st == 422, f"{st} {str(r)[:120]}")
st, r = req("POST", "/api/servicios", {"nombre": "x"}, token=admin)
check("nombre de 1 letra -> 422", st == 422, f"{st} {str(r)[:120]}")

# =====================================================================
print("\n== 5. Sólo el ADMIN ==")
if operador:
    st, r = req("POST", "/api/servicios", {"nombre": "Operador no puede"},
                token=operador)
    check("un operador NO crea servicios -> 403", st == 403,
          f"{st} {str(r)[:150]}")
    st, r = req("DELETE", f"/api/servicios/{nuevo['id']}", token=operador)
    check("un operador NO borra servicios -> 403", st == 403,
          f"{st} {str(r)[:150]}")
    # El servicio no se creó de ahi: sigue el del admin.
    st, lista3 = req("GET", "/api/servicios", token=admin)
    check("el intento del operador no creó nada",
          not [s for s in lista3 if s["nombre"] == "Operador no puede"],
          str([s["nombre"] for s in lista3]))
else:
    print("      (no hay usuario operador: se saltean los checks de permisos)")

# =====================================================================
print("\n== 6. Borrado ==")
st, r = req("DELETE", f"/api/servicios/{nuevo['id']}", token=admin)
check("un servicio SIN clientes se borra -> 204", st == 204, f"{st} {str(r)[:150]}")
st, r = req("GET", f"/api/servicios/{nuevo['id']}", token=admin)
check("y ya no está", st == 404, str(st))
SERVICIOS.clear()

st, r = req("DELETE", "/api/servicios/999999", token=admin)
check("borrar uno inexistente -> 404", st == 404, str(st))

# --- con clientes: NO se borra -------------------------------------------
print("\n  Ahora uno CON clientes:")
st, con_cli = req("POST", "/api/servicios", {"nombre": "Prueba con cliente"},
                  token=admin)
check("se crea", st == 201, f"{st} {str(con_cli)[:120]}")

st, cli = req("GET", "/api/clientes", token=admin)
base = next((c for c in cli if c.get("dni") or c.get("cuit")), None)
if base is None:
    print("      (no hay cliente base: no se prueba el borrado con clientes)")
else:
    # El DNI se arma con el id del servicio para que sea único por corrida.
    # Con uno fijo (tipo 31777888) la segunda corrida falla con "Ya existe una
    # persona con ese DNI", porque el de la corrida anterior quedó sin borrar
    # — y eso no es un error del catálogo, sino del test.
    dni = f"3{con_cli['id']:07d}"[-8:]
    st, creado = req("POST", "/api/clientes", {
        "tipo_persona": "fisica",
        "nombre": "Prueba", "apellido": "Servicio",
        "dni": dni,
        "actividad_economica": "servicios",
        "tipo_actividad": "responsable_inscripto",
        "condicion_iva": "responsable_inscripto",
        "servicios": [con_cli["id"]],
    }, token=admin)
    check("el cliente se crea con ese servicio elegido", st == 201,
          f"{st} {str(creado)[:150]}")
    if st == 201:
        CLIENTES.append(creado["id"])

        # Y el servicio queda efectivamente asignado (no solo aceptado).
        st, ficha = req("GET", f"/api/clientes/{creado['id']}", token=admin)
        elegidos = [s for s in (ficha.get("servicios") or []) if s["id"] == con_cli["id"]]
        check("el servicio quedó asignado al cliente", bool(elegidos),
              str(ficha.get("servicios")))

        st, r = req("DELETE", f"/api/servicios/{con_cli['id']}", token=admin)
        check("un servicio CON clientes NO se borra -> 409", st == 409,
              f"{st} {str(r)[:150]}")
        check("y el error explica por qué (cuántos clientes)",
              st == 409 and "cliente" in str(r.get("detail", "")),
              str(r.get("detail")))

        st, sigue = req("GET", f"/api/servicios/{con_cli['id']}", token=admin)
        check("el servicio sigue existiendo", st == 200, str(st))
    SERVICIOS.append(con_cli["id"])

# =====================================================================
print("\n== 7. Limpiar ==")
# Primero los clientes (tienen `cliente_servicio` con FK RESTRICT al servicio),
# después los servicios. Al revés, MySQL rebota.
db = SessionLocal()
try:
    for cid in CLIENTES:
        db.execute(text("DELETE FROM cliente_servicio WHERE cliente_id = :c"), {"c": cid})
        db.execute(text("DELETE FROM clientes WHERE id = :c"), {"c": cid})
    for sid in SERVICIOS:
        db.execute(text("DELETE FROM cliente_servicio WHERE servicio_id = :s"), {"s": sid})
        db.execute(text("DELETE FROM servicios WHERE id = :s"), {"s": sid})
    db.commit()
finally:
    db.close()

st, fin = req("GET", "/api/servicios", token=admin)
check("no quedó ningún servicio de prueba",
      not [s for s in fin if s["nombre"].startswith("Prueba")],
      str([s["nombre"] for s in fin if s["nombre"].startswith("Prueba")]))
check("el catálogo quedó con los servicios de verdad", len(fin) == 10,
      f"{len(fin)} servicios")

print(f"\n{ok} OK / {len(fallos)} fallos")
if fallos:
    raise SystemExit(1)