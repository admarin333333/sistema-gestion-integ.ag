"""Pruebas de la Fase 3 — recibos, aplicación entre facturas y cuenta corriente."""

import json
import os
import urllib.error
import urllib.parse
import urllib.request

# La dirección de la API sale de `GC_BASE_URL` para poder correr estas pruebas
# contra la base de PRUEBAS y no contra la del estudio. Si la variable no
# está, usa 8010 como antes: no cambia cómo se corren.
BASE = os.environ.get("GC_BASE_URL", "http://127.0.0.1:8010")

# Esta suite habla con la base de DOS maneras: por HTTP (`BASE`) y por SQL directo
# (`app.database`, para limpiar lo que dejó la corrida). Con solo `GC_BASE_URL` el
# SQL se va a la base REAL y la limpieza no borra nada de la base de pruebas.
#
# `DB_NAME` tiene que estar puesta ANTES de que se importe `app.database` (abajo,
# en el bloque de imports), porque ese módulo lee el entorno UNA sola vez al
# importarse.
if "GC_BASE_URL" in os.environ:
    os.environ.setdefault(
        "DB_NAME", os.environ.get("GC_TEST_DB", "gestion_contable_test")
    )

resultado = []


def pedir(metodo, ruta, token=None, cuerpo=None):
    datos = None
    encabezados = {"Content-Type": "application/json"}
    if token:
        encabezados["Authorization"] = f"Bearer {token}"
    if cuerpo is not None:
        datos = json.dumps(cuerpo).encode("utf-8")
    req = urllib.request.Request(
        BASE + urllib.parse.quote(ruta, safe="/?&=:%,-."),
        data=datos,
        headers=encabezados,
        method=metodo,
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            texto = resp.read().decode("utf-8")
            return resp.status, json.loads(texto) if texto else None
    except urllib.error.HTTPError as e:
        texto = e.read().decode("utf-8")
        try:
            return e.code, json.loads(texto) if texto else None
        except json.JSONDecodeError:
            return e.code, {"detail": texto}


def chequear(nombre, condicion, detalle=""):
    resultado.append((nombre, bool(condicion), detalle))


def login(usuario, password):
    codigo, datos = pedir(
        "POST", "/api/auth/login", cuerpo={"usuario": usuario, "password": password}
    )
    return datos.get("access_token") if codigo == 200 else None


admin = login("admin", "admin123")
operador = login("operador", "operador123")
chequear("Login admin", admin is not None)
chequear("Login operador", operador is not None)

DNI_A = "39777666"
DNI_B = "39777667"


def borrar_cliente_si_existe(dni, token):
    """Limpia restos de una corrida anterior (facturas, recibos, aplicaciones)."""
    codigo, encontrados = pedir("GET", f"/api/clientes?q={dni}", token)
    for cliente in encontrados or []:
        cid = cliente["id"]
        _, facturas = pedir("GET", f"/api/facturas?cliente_id={cid}", token)
        for f in facturas or []:
            pedir("DELETE", f"/api/facturas/{f['id']}", token)
        _, recibos = pedir("GET", f"/api/recibos?cliente_id={cid}", token)
        for r in recibos or []:
            _, aplicaciones = pedir("GET", f"/api/recibos/{r['id']}/aplicaciones", token)
            for a in aplicaciones or []:
                pedir("DELETE", f"/api/recibos/aplicaciones/{a['id']}", token)
            pedir("DELETE", f"/api/recibos/{r['id']}", token)
        pedir("DELETE", f"/api/clientes/{cid}", token)


borrar_cliente_si_existe(DNI_A, admin)
borrar_cliente_si_existe(DNI_B, admin)


def crear_cliente(nombre, dni):
    codigo, datos = pedir(
        "POST",
        "/api/clientes",
        admin,
        {
            "tipo_persona": "fisica",
            "nombre": nombre,
            "apellido": "Recibos",
            "dni": dni,
            "actividad_economica": "servicios",
            "tipo_actividad": "monotributista",
    "condicion_iva": "monotributista",
            "servicios": [1],
        },
    )
    if codigo == 409:
        _, existentes = pedir("GET", f"/api/clientes?q={dni}", admin)
        datos = existentes[0]
    return datos


cliente_a = crear_cliente("Ana", DNI_A)
cliente_b = crear_cliente("Bruno", DNI_B)
chequear("Cliente A listo", cliente_a is not None, str(cliente_a))
chequear("Cliente B listo", cliente_b is not None, str(cliente_b))
ca = cliente_a["id"]
cb = cliente_b["id"]

FACTURA_BASE = {
    "cliente_id": ca,
    "fecha": "2026-09-10",
    "tipo_comprobante": "factura_b",
    "punto_venta": "1",
    "numero": "100",
    "concepto": "Trabajo de septiembre",
    "importe": 100000,
    "fecha_vencimiento": "2026-09-25",
    "condicion_venta": "cta_corriente_30",
    "cae": "",
    "cae_vencimiento": None,
}

_, f1 = pedir("POST", "/api/facturas", admin, {**FACTURA_BASE, "numero": "100"})
_, f2 = pedir(
    "POST", "/api/facturas", admin,
    {**FACTURA_BASE, "numero": "101", "fecha": "2026-09-12", "importe": 50000},
)
_, f3 = pedir(
    "POST", "/api/facturas", admin,
    {**FACTURA_BASE, "numero": "102", "fecha": "2026-09-14", "importe": 30000},
)
_, factura_otro = pedir(
    "POST", "/api/facturas", admin,
    {**FACTURA_BASE, "cliente_id": cb, "numero": "103", "importe": 70000},
)
chequear(
    "Facturas de prueba listas",
    all(x and x.get("id") for x in (f1, f2, f3, factura_otro)),
    str([x.get("id") for x in (f1, f2, f3, factura_otro) if x]),
)

# ----------------------------------------------------------------- sin token
codigo, _ = pedir("GET", "/api/recibos", None)
chequear("Sin token -> 401", codigo == 401, str(codigo))

# ----------------------------------------------------------------- listado
codigo, lista = pedir("GET", "/api/recibos", admin)
chequear("GET /recibos -> 200 y lista", codigo == 200 and isinstance(lista, list), str(codigo))

# --------------------------------------------------------------------- alta
RECIBO = {
    "cliente_id": ca,
    "fecha": "2026-09-20",
    "importe": 150000,
    "forma_pago": "transferencia",
}
codigo, r1 = pedir("POST", "/api/recibos", admin, RECIBO)
chequear("Alta recibo -> 201", codigo == 201, str(codigo))
# El número se genera solo y es GLOBAL (no por cliente): con recibos viejos en
# la base el primero puede no ser 00000001, así que se verifica el formato.
numero_r1 = (r1 or {}).get("numero") or ""
chequear(
    "Número generado solo (8 dígitos)",
    len(numero_r1) == 8 and numero_r1.isdigit(),
    str(numero_r1),
)
chequear("Trae el nombre del cliente", r1 and r1.get("cliente_nombre") == "Recibos, Ana", str(r1 and r1.get("cliente_nombre")))

# El número NO se carga a mano: si viene, el backend lo rechaza y lo dice.
codigo, repetido = pedir("POST", "/api/recibos", admin, {**RECIBO, "numero": numero_r1})
chequear("Número cargado a mano -> 400", codigo == 400, str(codigo))
chequear(
    "Aviso claro de que el número se genera solo",
    "se genera solo" in str(repetido),
    str(repetido),
)

for campo, valor in (
    ("forma_pago", "bitcoin"),
    ("importe", 0),
    ("importe", -10),
):
    codigo, datos = pedir("POST", "/api/recibos", admin, {**RECIBO, campo: valor})
    chequear(f"{campo}={valor} rechazado (422)", codigo == 422, f"{codigo} {datos}")

codigo, datos = pedir("POST", "/api/recibos", admin, {**RECIBO, "numero": "abc"})
chequear("numero=abc rechazado (400)", codigo == 400, f"{codigo} {datos}")

codigo, datos = pedir("POST", "/api/recibos", admin, {**RECIBO, "cliente_id": 99999})
chequear("Cliente inexistente -> 404", codigo == 404, f"{codigo} {datos}")

codigo, datos = pedir("GET", "/api/recibos/99999", admin)
chequear("Recibo inexistente -> 404", codigo == 404, str(codigo))

# ------------------------------------------------------------- edición
codigo, editado = pedir("PUT", f"/api/recibos/{r1['id']}", admin, {**RECIBO, "importe": 150000, "forma_pago": "efectivo"})
chequear("Modificar recibo -> 200", codigo == 200, str(codigo))
chequear("Se cambió la forma de pago", editado and editado.get("forma_pago") == "efectivo", str(editado and editado.get("forma_pago")))

# ------------------------------------------------------------ aplicar
codigo, a1 = pedir(
    "POST", f"/api/recibos/{r1['id']}/aplicaciones", admin,
    {"factura_id": f1["id"], "importe": 100000},
)
chequear("Aplicar a factura completa -> 201", codigo == 201, str(codigo))
chequear("La aplicación trae la factura", a1 and a1.get("factura", {}).get("numero") == "00000100", str(a1))

_, f1_leida = pedir("GET", f"/api/facturas/{f1['id']}", admin)
chequear("Factura queda PAGADA", f1_leida.get("estado") == "pagada", str(f1_leida.get("estado")))

codigo, a2 = pedir(
    "POST", f"/api/recibos/{r1['id']}/aplicaciones", admin,
    {"factura_id": f2["id"], "importe": 30000},
)
_, f2_leida = pedir("GET", f"/api/facturas/{f2['id']}", admin)
chequear("Pago parcial -> estado parcial", f2_leida.get("estado") == "parcial", str(f2_leida.get("estado")))

codigo, datos = pedir(
    "POST", f"/api/recibos/{r1['id']}/aplicaciones", admin,
    {"factura_id": f3["id"], "importe": 99999},
)
chequear("Se pasa del recibo -> 409", codigo == 409, str(codigo))
chequear(
    "Avisa cuánto le queda al recibo",
    "20000.00" in str(datos) or "20,000.00" in str(datos),
    str(datos),
)

codigo, datos = pedir(
    "POST", f"/api/recibos/{r1['id']}/aplicaciones", admin,
    {"factura_id": factura_otro["id"], "importe": 1000},
)
chequear("Factura de otro cliente -> 409", codigo == 409, str(codigo))

codigo, _ = pedir("POST", f"/api/facturas/{f3['id']}/anular", admin)
codigo, datos = pedir(
    "POST", f"/api/recibos/{r1['id']}/aplicaciones", admin,
    {"factura_id": f3["id"], "importe": 1000},
)
chequear("Factura anulada -> 409", codigo == 409, str(codigo))
pedir("POST", f"/api/facturas/{f3['id']}/reabrir", admin)

codigo, aplicaciones = pedir("GET", f"/api/recibos/{r1['id']}/aplicaciones", admin)
chequear("El recibo tiene 2 aplicaciones", codigo == 200 and len(aplicaciones) == 2, str(len(aplicaciones or [])))

# recibo 150000 → aplicados 130000 → queda 20000
codigo, datos = pedir(
    "POST", f"/api/recibos/{r1['id']}/aplicaciones", admin,
    {"factura_id": f2["id"], "importe": 25000},
)
chequear("Se pasa de lo que falta en la factura -> 409", codigo == 409, str(datos))

# --------------------------------------------------------------- roles
codigo, datos = pedir(
    "POST", f"/api/recibos/{r1['id']}/aplicaciones", operador,
    {"factura_id": f3["id"], "importe": 5000},
)
chequear("Operador puede aplicar -> 201", codigo == 201, str(codigo))

codigo, datos = pedir("DELETE", f"/api/recibos/aplicaciones/{a1['id']}", operador)
chequear("Operador NO desaplica -> 403", codigo == 403, str(codigo))

codigo, datos = pedir("DELETE", f"/api/recibos/{r1['id']}", operador)
chequear("Operador NO borra recibo -> 403", codigo == 403, str(codigo))

codigo, datos = pedir("POST", "/api/recibos", operador, RECIBO)
chequear("Operador crea recibo -> 201", codigo == 201, str(codigo))
r2 = datos

codigo, datos = pedir("DELETE", f"/api/recibos/{r2['id']}", admin)
chequear("Recibo sin aplicaciones se borra -> 204", codigo == 204, str(codigo))

codigo, datos = pedir("DELETE", f"/api/recibos/{r1['id']}", admin)
chequear("Recibo con aplicaciones NO se borra -> 409", codigo == 409, str(codigo))

# ------------------------------------------------------ bajar importe aplicado
codigo, datos = pedir("PUT", f"/api/recibos/{r1['id']}", admin, {**RECIBO, "importe": 50000})
chequear("No se puede bajar el importe por debajo de lo aplicado -> 409", codigo == 409, str(datos))

# ------------------------------------------------------------- desaplicar
codigo, datos = pedir("DELETE", f"/api/recibos/aplicaciones/{a1['id']}", admin)
chequear("Desaplicar (admin) -> 204", codigo == 204, str(codigo))

_, f1_final = pedir("GET", f"/api/facturas/{f1['id']}", admin)
chequear("Al desaplicar vuelve a pendiente", f1_final.get("estado") == "pendiente", str(f1_final.get("estado")))

codigo, datos = pedir("DELETE", "/api/recibos/aplicaciones/99999", admin)
chequear("Aplicación inexistente -> 404", codigo == 404, str(codigo))

# ------------------------------------------------------ cuenta corriente
codigo, cc = pedir("GET", f"/api/clientes/{ca}/cuenta", admin)
chequear("Cuenta corriente -> 200", codigo == 200, str(codigo))
chequear("Trae el nombre", cc and cc.get("cliente_nombre") == "Recibos, Ana", str(cc and cc.get("cliente_nombre")))

mov = cc.get("movimientos", [])
chequear("Hay 4 movimientos (3 facturas + 1 recibo)", len(mov) == 4, str([m["concepto"] for m in mov]))

chequear(
    "Conceptos legibles",
    any(m["concepto"].startswith("Factura B") for m in mov)
    and any(m["concepto"].startswith("Recibo") for m in mov),
    str([m["concepto"] for m in mov]),
)

# DEBE: 100000 + 50000 + 30000 = 180000   HABER: 150000 + recibo extra
chequear("Total DEBE = suma de facturas", abs(cc["total_debe"] - 180000) < 0.01, str(cc["total_debe"]))
chequear("Total HABER = suma de recibos", abs(cc["total_haber"] - 150000) < 0.01, str(cc["total_haber"]))
chequear("Saldo = DEBE - HABER", abs(cc["saldo"] - 30000) < 0.01, str(cc["saldo"]))
chequear(
    "El saldo final de la tabla coincide con el resumen",
    abs(mov[-1]["saldo"] - cc["saldo"]) < 0.01,
    f"{mov[-1]['saldo']} vs {cc['saldo']}",
)

acumulado = 0
saldo_ok = True
for m in mov:
    acumulado += m["debe"] - m["haber"]
    if abs(acumulado - m["saldo"]) > 0.01:
        saldo_ok = False
chequear("Saldo corrido fila por fila", saldo_ok, str([m["saldo"] for m in mov]))

codigo, cc_vacia = pedir("GET", f"/api/clientes/99999/cuenta", admin)
chequear("Cliente inexistente -> 404", codigo == 404, str(codigo))

codigo, _ = pedir("GET", f"/api/clientes/{ca}/cuenta", None)
chequear("Cuenta corriente sin token -> 401", codigo == 401, str(codigo))

# ------------------------------------------------------- bloqueos de cliente
codigo, datos = pedir("DELETE", f"/api/clientes/{ca}", admin)
chequear("Cliente con recibos NO se borra -> 409", codigo == 409, str(codigo))

# -------------------------------------------------------------- limpieza
_, aplicaciones = pedir("GET", f"/api/recibos/{r1['id']}/aplicaciones", admin)
for a in aplicaciones or []:
    pedir("DELETE", f"/api/recibos/aplicaciones/{a['id']}", admin)

_, restantes = pedir("GET", f"/api/facturas?cliente_id={ca}", admin)
for f in restantes or []:
    pedir("DELETE", f"/api/facturas/{f['id']}", admin)
pedir("DELETE", f"/api/recibos/{r1['id']}", admin)

_, restantes_b = pedir("GET", f"/api/facturas?cliente_id={cb}", admin)
for f in restantes_b or []:
    pedir("DELETE", f"/api/facturas/{f['id']}", admin)

_, quedan_f = pedir("GET", f"/api/facturas?cliente_id={ca}", admin)
_, quedan_r = pedir("GET", f"/api/recibos?cliente_id={ca}", admin)
chequear("Se limpiaron las facturas", quedan_f == [], str(quedan_f))
chequear("Se limpiaron los recibos", quedan_r == [], str(quedan_r))

# Los recibos que quedan los saca la API sola no puede: si tienen asiento,
# `asiento_origen` bloquea el borrado con 409 y el `DELETE` de arriba se come
# ese error sin mirar el código de respuesta. El resultado eran recibos con
# asiento contabilizado flotando en la base, que rompían el Mayor de documentos
# a cobrar y la numeración de las suites que corren después.
#
# `borrar_prueba` sabe el orden que mandan las FK (detalle → origen → asiento →
# recibo). Ver `borrar_prueba.py`.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
import borrar_prueba  # noqa: E402
from app.database import SessionLocal  # noqa: E402

_db = SessionLocal()
borrar_prueba.limpiar_todo(_db)
_db.close()

codigo, _ = pedir("DELETE", f"/api/clientes/{ca}", admin)
chequear("Se borra el cliente A", codigo in (200, 204), str(codigo))
codigo, _ = pedir("DELETE", f"/api/clientes/{cb}", admin)
chequear("Se borra el cliente B", codigo in (200, 204), str(codigo))

# ------------------------------------------------------------------ reporte
fallidos = [r for r in resultado if not r[1]]
for nombre, ok, detalle in resultado:
    print(f"  {'OK  ' if ok else 'FALLA'} {nombre}" + (f"  -> {detalle}" if not ok else ""))
print(f"\n{len(resultado) - len(fallidos)}/{len(resultado)} pruebas correctas.")
raise SystemExit(1 if fallidos else 0)
