"""Prueba el filtro por MÓDULO de asientos: RECIBO, FACTURA y MANUAL.

Verifica que cada módulo traiga SOLO lo suyo, y que MANUAL no traiga ningún
asiento que venga de un documento (FV, NC, ND, RC), que es justo lo que lo
distingue.
"""

import json
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8010"
resultado = []


def pedir(metodo, ruta, token=None, cuerpo=None):
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(BASE + ruta, data=datos, method=metodo)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            texto = r.read().decode()
            return r.status, json.loads(texto) if texto else None
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:250]


def chequear(nombre, condicion, detalle=""):
    resultado.append((nombre, bool(condicion), detalle))


token = pedir("POST", "/api/auth/login",
             cuerpo={"usuario": "admin", "password": "admin123"})[1]["access_token"]

RANGO = "desde=2000-01-01&hasta=2100-01-01"


def asientos_de(origen):
    _, d = pedir("GET", f"/api/asientos?{RANGO}" + (f"&origen={origen}" if origen else ""),
                 token)
    if d is None:
        return [], []
    filas = [a for dia in d["dias"] for a in dia["asientos"]]
    return d["dias"], filas


todos_dias, todos = asientos_de("")
_, facturas = asientos_de("FACTURA")
_, recibos = asientos_de("RECIBO")
_, manuales = asientos_de("MANUAL")

chequear("Sin filtro salen asientos", len(todos) > 0, str(len(todos)))
chequear("Los asientos vienen agrupados por día", len(todos_dias) > 0)
chequear(
    "Cada día trae sus totales (los calcula SQL)",
    all("total_debe" in dia and "total_haber" in dia for dia in todos_dias),
)

codigos_factura = {a["codigo_comprobante"] for a in facturas if a["codigo_comprobante"]}
chequear(
    "El módulo Facturas solo trae FV, NC o ND",
    codigos_factura <= {"FV", "NC", "ND"},
    str(codigos_factura),
)
chequear("El módulo Facturas trae algo", len(facturas) > 0, str(len(facturas)))

codigos_recibo = {a["codigo_comprobante"] for a in recibos if a["codigo_comprobante"]}
chequear("El módulo Recibos solo trae RC", codigos_recibo <= {"RC"}, str(codigos_recibo))
chequear("El módulo Recibos trae algo", len(recibos) > 0, str(len(recibos)))

# La clave: los módulos de documento y el manual NO se pisan.
chequear(
    "Facturas y Recibos no comparten ningún asiento",
    not ({a["id_asiento"] for a in facturas} & {a["id_asiento"] for a in recibos}),
)
chequear(
    "Recibos y Manuales no comparten ningún asiento",
    not ({a["id_asiento"] for a in recibos} & {a["id_asiento"] for a in manuales}),
)

codigos_manual = {a["codigo_comprobante"] for a in manuales}
chequear(
    "Manual NO trae asientos que vengan de un documento",
    not (codigos_manual & {"FV", "NC", "ND", "RC"}),
    str(codigos_manual),
)
chequear(
    "Los tres módulos juntos dan todos los asientos",
    len({a["id_asiento"] for a in facturas + recibos + manuales})
    == len({a["id_asiento"] for a in todos}),
    f"{len(facturas) + len(recibos) + len(manuales)} vs {len(todos)}",
)

# Un módulo inventado se rechaza, no devuelve todo.
codigo, error = pedir("GET", f"/api/asientos?{RANGO}&origen=INVENTADO", token)
chequear("Un módulo que no existe se rechaza con 400", codigo == 400, str(codigo))

fallos = [r for r in resultado if not r[1]]
for nombre, ok, detalle in resultado:
    if not ok:
        print(f"  FALLA  {nombre}  {detalle}")
print()
print(f"  {len(resultado) - len(fallos)}/{len(resultado)} pruebas correctas")
if not fallos:
    print("  Todas en verde.")
else:
    print(f"  {len(fallos)} FALLOS")
raise SystemExit(1 if fallos else 0)