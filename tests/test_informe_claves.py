# Prueba del informe de CUIT y clave fiscal
import json
import time
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8010"
ok = 0
fallos = []


def req(metodo, ruta, datos=None, token=None, binario=False):
    r = urllib.request.Request(BASE + ruta, method=metodo)
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", "Bearer " + token)
    cuerpo = json.dumps(datos).encode() if datos is not None else None
    try:
        with urllib.request.urlopen(r, cuerpo, timeout=30) as resp:
            d = resp.read()
            return resp.status, (d if binario else (json.loads(d) if d else None))
    except urllib.error.HTTPError as e:
        d = e.read().decode() or "{}"
        try:
            return e.code, json.loads(d)
        except json.JSONDecodeError:
            return e.code, {"detalle": d}


def check(nombre, cond, detalle=""):
    global ok
    if cond:
        ok += 1
        print(f"  OK  {nombre}")
    else:
        fallos.append(nombre)
        print(f"FALLA {nombre} -> {detalle}")


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

# --- El informe de proveedores (estaba roto con 500) ---
st, pv = req("GET", "/api/informes/proveedores", token=token)
check("informe de proveedores ya no da 500", st == 200, f"{st} {str(pv)[:120]}")

BASE_HEAD = {
    "tipo_persona": "juridica", "actividad_economica": "servicios",
    "tipo_actividad": "responsable_inscripto", "condicion_iva": "responsable_inscripto",
}
# Juan (cuit ...-2), Distribuidora (...-8) y uno nuevo (...-5)
datos = [
    ("INFORME CF UNO", "30-11111111-8", "INFUNO12345"),   # 11 caracteres
    ("INFORME CF DOS", "20-22222222-3", "INFDOS56789"),   # 11 caracteres
]
ids = []
for nombre, cuit, clave in datos:
    st, c = req("POST", "/api/clientes",
                dict(BASE_HEAD, nombre=nombre, cuit=cuit,
                     clave_fiscal=clave, servicios=[]), token)
    check(f"crea {nombre}", st == 201, f"{st} {str(c)[:100]}")
    if st == 201:
        ids.append(c["id"])

# --- Informe sin filtros ---
#
# OJO con `inf["cantidad"]`: el informe trae TODOS los clientes con clave
# fiscal, no solo los de este test. Si otro test dejó alguno (y los hay: el
# informe por clave fiscal es de datos reales), el número no es 2 y el test
# falla sin que el informe esté mal.
#
# Por eso se mide sobre los IDs de este test: se filtran los items por id y se
# cuenta sobre ese subconjunto. Si el filtro de la API o la creación del cliente
# no funcionan, el subconjunto da 0 y el test avisa.
st, inf = req("GET", "/api/informes/claves-fiscales", token=token)
check("informe responde", st == 200, f"{st} {str(inf)[:120]}")
if st == 200:
    mios = [i for i in inf["items"] if i["id"] in ids]
    check("trae los 2 clientes que creó este test", len(mios) == 2,
          f"{len(mios)} de {len(inf['items'])} en total")
    check("trae los sin clave aparte", inf["cantidad_sin_clave"] >= 3,
          str(inf["cantidad_sin_clave"]))
    check("cada item trae el último dígito",
          all("ultimo_digito" in i for i in inf["items"]), "")
    digitos = {i["ultimo_digito"] for i in mios}
    check("los dígitos son 8 y 3", digitos == {"8", "3"}, str(sorted(digitos)))
    # OJO con la comparación: en `items` el dígito viene como TEXTO ('3') y en
    # `bloques` como NÚMERO (3). Comparar '3' == 3 da False y el test falla sin
    # que el informe esté mal. Por eso se pasa todo a texto con str().
    digitos_bloques = {str(b["ultimo_digito"]) for b in inf["bloques"]}
    for d in sorted(digitos):
        bloque = next((b for b in inf["bloques"] if str(b["ultimo_digito"]) == d),
                      None)
        check(f"hay bloque para el dígito {d}", bloque is not None,
              str(sorted(digitos_bloques)))
        check(f"  y el cliente de este test está en ese bloque",
              bloque is not None
              and any(i["id"] in ids for i in bloque["items"]),
              str(bloque["items"]) if bloque else "")
    check("cada bloque trae sus items con la cantidad correcta",
          all(b["items"] and b["cantidad"] == len(b["items"])
              for b in inf["bloques"]), "")
    check("los sin clave vienen sin clave_fiscal",
          all(not i["clave_fiscal"] for i in inf["sin_clave"]), "")

# --- Filtro por terminación ---
# Ojo: el CUIT 20-22222222-3 termina en 3, no en 5 (el dígito verificador es
# el último, así que al corregirlo cambió la terminación).
st, r = req("GET", "/api/informes/claves-fiscales?terminacion=3", token=token)
# Otra vez sobre los propios: la terminación 3 la tienen los datos de este test,
# pero puede haber más clientes que terminen en 3 en la base.
mios3 = [i for i in r["items"] if i["id"] in ids]
check("filtra por terminación 3 y trae al de este test",
      st == 200 and len(mios3) == 1, f"{st} {len(mios3)} de {r.get('cantidad')}")
check("el que queda es el correcto",
      mios3 and mios3[0]["cuit"] == "20-22222222-3",
      str(mios3[0]["cuit"]) if mios3 else "no vino")
st, r = req("GET", "/api/informes/claves-fiscales?terminacion=8", token=token)
mios8 = [i for i in r["items"] if i["id"] in ids]
check("filtra por terminación 8 y trae al de este test",
      len(mios8) == 1 and mios8[0]["ultimo_digito"] == "8",
      f"{len(mios8)} de {r['cantidad']}")
st, r = req("GET", "/api/informes/claves-fiscales?terminacion=7", token=token)
check("terminación sin clientes da 0", r["cantidad"] == 0, str(r["cantidad"]))
st, r = req("GET", "/api/informes/claves-fiscales?terminacion=99", token=token)
check("rechaza terminación fuera de 0 a 9", st == 422, str(st))

# --- Filtro por fecha de carga de la clave ---
st, r = req("GET", "/api/informes/claves-fiscales?desde=2000-01-01&hasta=2000-12-31",
            token=token)
check("filtro de fechas que no incluye nada da 0", r["cantidad"] == 0, str(r["cantidad"]))
st, r = req("GET", "/api/informes/claves-fiscales?desde=2000-01-01&hasta=2099-12-31",
            token=token)
check("filtro de fechas amplio trae los 2 de este test",
      len([i for i in r["items"] if i["id"] in ids]) == 2,
      f"{len([i for i in r['items'] if i['id'] in ids])} de {r['cantidad']}")
check("trae la fecha de carga y la de modificación",
      all(i["fecha_carga_clave_fiscal"] and i["fecha_modif_clave_fiscal"] for i in r["items"]),
      str(r["items"][0]))

# --- Excel ---
st, xls = req("GET", "/api/informes/claves-fiscales/export.xlsx", token=token, binario=True)
check("exporta Excel", st == 200 and xls[:2] == b"PK", f"{st} {len(xls or b'')}")
check("el Excel no está vacío", len(xls or b"") > 3000, str(len(xls or b"")))
st, xls2 = req("GET", "/api/informes/claves-fiscales/export.xlsx?terminacion=3",
               token=token, binario=True)
check("el Excel respeta el filtro", st == 200 and (xls2 or b"") != xls, str(st))

# --- No cruza con proveedores ---
st, pv = req("GET", "/api/informes/claves-fiscales", token=token)
nombres = {i["nombre"] for i in pv["items"]}
check("solo trae clientes, no proveedores", all("PROVEEDOR" not in n.upper() for n in nombres),
      str(nombres))

# --- limpieza
for cid in ids:
    req("DELETE", f"/api/clientes/{cid}", token=token)
st, fin = req("GET", "/api/informes/claves-fiscales", token=token)
# No se mide `fin["cantidad"] == 0`: quedan los clientes REALES que ya tenían
# clave fiscal. Lo que tiene que ser 0 son los de ESTE test.
check("limpia los clientes de prueba",
      not [i for i in fin["items"] if i["id"] in ids],
      str([i["nombre"] for i in fin["items"] if i["id"] in ids]))

print(f"\n{ok} OK / {len(fallos)} fallos")
if fallos:
    raise SystemExit(1)