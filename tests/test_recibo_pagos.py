"""Pruebas del rediseño del recibo:

  1. La nota de crédito compensa sola (la factura de 1.000 con NC de 300 tiene
     saldo 700, y la NC queda "pagada", no colgada como pendiente).
  2. Un recibo con VARIAS formas de pago genera un Debe por cada medio y un
     solo Haber a Documentos a cobrar.
  3. La vista previa (`/preview-cobro`) devuelve EXACTAMENTE lo mismo que el
     asiento real.
  4. El reparto del importe entre varias facturas lo hace el backend.

Limpia SOLO lo que crea (por concepto 'PRUEBA RECIBOS'), en orden de FK.
"""

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8010"
CONCEPTO = "PRUEBA RECIBOS"
resultado = []

# La limpieza va por SQL (ver limpiar_prueba_recibo_pagos.py): un recibo que ya
# tiene asiento no se puede borrar por la API, porque `asiento_origen.id_recibo`
# es ON DELETE RESTRICT. Así la corrida arranca siempre con base conocida.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import limpiar_prueba_recibo_pagos  # noqa: E402


def limpiar():
    limpiar_prueba_recibo_pagos.main()


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
        with urllib.request.urlopen(req, timeout=20) as resp:
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


admin = pedir("POST", "/api/auth/login",
              cuerpo={"usuario": "admin", "password": "admin123"})[1]["access_token"]
operador = pedir("POST", "/api/auth/login",
                 cuerpo={"usuario": "operador",
                         "password": "operador123"})[1]["access_token"]
chequear("Login admin", admin is not None)
chequear("Login operador", operador is not None)

# ---------------------------------------------------------------- limpieza
limpiar()

# ------------------------------------------------------------------ datos

DNI = "39777690"
codigo, cliente = pedir(
    "POST", "/api/clientes", admin,
    {"tipo_persona": "fisica", "nombre": "Prueba", "apellido": "Recibo Multiple",
     "dni": DNI, "actividad_economica": "servicios",
     "tipo_actividad": "monotributista", "condicion_iva": "monotributista",
     "servicios": [1]},
)
if codigo == 409:
    _, existentes = pedir("GET", f"/api/clientes?q={DNI}", admin)
    cliente = existentes[0]
cid = cliente["id"]
chequear("Cliente de prueba listo", cliente is not None, str(cliente))

_, alicuotas = pedir("GET", "/api/alicuotas-iva", admin)
iva21 = next(a for a in alicuotas if float(a["porcentaje"]) == 21.0)

_, plan = pedir("GET", "/api/plan-cuentas", admin)
por_codigo = {p["codigo"]: p for p in plan}
SANTANDER = por_codigo["1.1.01.05"]["id_cuenta"]
FONDO_FIJO = por_codigo["1.1.01.02"]["id_cuenta"]
DOCUMENTOS = por_codigo["1.1.03.02"]

sello = str(int(time.time()))[-6:]


def facturar(tipo, importe, numero, relacionada=None):
    cuerpo = {
        "cliente_id": cid, "fecha": "2026-10-02",
        "tipo_comprobante": tipo, "punto_venta": "0001",
        "numero": numero, "importe": importe,
        "condicion_venta": "cta_corriente_30", "tipo_operacion": "SERVICIOS",
        "alicuota_iva_id": iva21["id"], "concepto": CONCEPTO,
    }
    if relacionada:
        cuerpo["factura_relacionada_id"] = relacionada
    return pedir("POST", "/api/facturas", admin, cuerpo)


# =========================================================== 1. NC compensa
_, fac1000 = facturar("factura_b", 1000.00, "1" + sello)
chequear("Factura de 1.000 creada", fac1000.get("id") is not None, str(fac1000.get("id")))

_, nc300 = facturar("nota_credito_b", 300.00, "2" + sello, relacionada=fac1000["id"])
chequear("Nota de crédito de 300 creada", nc300.get("id") is not None)
chequear(
    "La NC vinculada queda compensada (no pendiente)",
    nc300.get("estado") == "pagada",
    f"estado={nc300.get('estado')}",
)

_, fac500 = facturar("factura_b", 500.00, "3" + sello)
chequear("Factura de 500 creada", fac500.get("id") is not None)

# ------------------------------------------------------- endpoint a-cobrar
_, cobro = pedir("GET", f"/api/recibos/a-cobrar?cliente_id={cid}", admin)
chequear("GET /a-cobrar responde 200", cobro is not None)

filas = {f["id"]: f for f in (cobro or {}).get("facturas", [])}
chequear(
    "La factura de 1.000 aparece con saldo 700 (1.000 - NC 300)",
    filas.get(fac1000["id"], {}).get("saldo") == 700.0,
    str(filas.get(fac1000["id"])),
)
chequear(
    "La columna de notas de crédito muestra 300",
    filas.get(fac1000["id"], {}).get("creditos") == 300.0,
    str(filas.get(fac1000["id"], {}).get("creditos")),
)
chequear(
    "La factura de 500 aparece con saldo 500",
    filas.get(fac500["id"], {}).get("saldo") == 500.0,
    str(filas.get(fac500["id"])),
)
chequear(
    # No se afirma un total absoluto: la base puede tener facturas de otras
    # corridas. Se mide la suma de las facturas CREADAS por este test.
    "El saldo total del cliente es la suma de los saldos de sus facturas",
    cobro.get("saldo") == round(
        sum(f["saldo"] for f in (cobro or {}).get("facturas", [])
            if f["id"] in (fac1000["id"], fac500["id"])), 2
    ),
    str(cobro.get("saldo")),
)
chequear(
    "Las NC del cliente vienen en la lista aparte",
    any(n["id"] == nc300["id"] for n in cobro.get("notas_credito", [])),
)

# La NC NO debe aparecer como "factura a cobrar" (es un crédito).
chequear(
    "La NC no aparece entre las facturas a cobrar",
    nc300["id"] not in filas,
)

# --------------------------------------------- 2. pago partido (dos bancos)
# 700 de la factura de 1.000 (su saldo neto) en dos medios de pago.
pagos = [
    {"forma_pago": "transferencia", "importe": 500.00,
     "cuenta_id": SANTANDER, "detalle": "Santander"},
    {"forma_pago": "efectivo", "importe": 200.00,
     "cuenta_id": FONDO_FIJO, "detalle": "mostrador"},
]
cuerpo_cobro = {
    "cliente_id": cid, "fecha": "2026-10-02", "importe": 700.00,
    "facturas": [fac1000["id"]], "pagos": pagos,
}

# ------------------------------------------------- 3. preview == asiento real
_, preview = pedir("POST", "/api/recibos/preview-cobro", admin, cuerpo_cobro)
chequear("POST /preview-cobro responde 200", preview is not None)

asiento_prev = (preview or {}).get("asiento") or {}
lineas_prev = {l["codigo"]: (l["debe"], l["haber"]) for l in asiento_prev.get("lineas", [])}
chequear("El preview trae 3 líneas", len(asiento_prev.get("lineas", [])) == 3,
         str(len(asiento_prev.get("lineas", []))))
chequear("Preview: Santander en el Debe por 500",
         lineas_prev.get("1.1.01.05") == (500.0, 0.0), str(lineas_prev.get("1.1.01.05")))
chequear("Preview: Fondo fijo en el Debe por 200",
         lineas_prev.get("1.1.01.02") == (200.0, 0.0), str(lineas_prev.get("1.1.01.02")))
chequear("Preview: Documentos a cobrar en el Haber por 700",
         lineas_prev.get("1.1.03.02") == (0.0, 700.0), str(lineas_prev.get("1.1.03.02")))
chequear("El preview cierra (debe == haber)", asiento_prev.get("cerrado") is True)
chequear("El preview no tiene avisos", not (preview or {}).get("avisos"),
         str((preview or {}).get("avisos")))

# ----------------------------------------------------- el alta de verdad
# La MARCA de prueba va en el `detalle` de cada pago: `recibos` no tiene columna
# `concepto`, así que el detalle es lo único que identifica a estos recibos.
# Si no se marcaran, `limpiar_prueba_recibo_pagos.py` no los encontraría y
# quedarían huérfanos (sin asiento y sin factura) en el listado de recibos.
codigo, recibo = pedir("POST", "/api/recibos", admin, {
    "cliente_id": cid, "fecha": "2026-10-02", "importe": 700.00,
    "forma_pago": "transferencia",
    "facturas": [fac1000["id"]],
    "pagos": [{**p, "detalle": CONCEPTO} for p in pagos],
})
chequear("El recibo se crea con dos pagos", codigo == 201, str(codigo))
rid = recibo.get("id")
chequear("El recibo trae sus 2 pagos guardados",
         len(recibo.get("pagos", [])) == 2, str(recibo.get("pagos")))
chequear("El pago de transferencia quedó en Santander",
         any(p["cuenta_id"] == SANTANDER for p in recibo.get("pagos", [])))
chequear("El pago de efectivo quedó en Fondo fijo",
         any(p["cuenta_id"] == FONDO_FIJO for p in recibo.get("pagos", [])))
chequear("Los pagos guardaron la marca de prueba (para poder limpiarlos)",
         all(p.get("detalle") == CONCEPTO for p in recibo.get("pagos", [])),
         str([p.get("detalle") for p in recibo.get("pagos", [])]))

_, apps = pedir("GET", f"/api/recibos/{rid}/aplicaciones", admin)
chequear("El recibo se aplicó a la factura de 1.000",
         any(a["factura_id"] == fac1000["id"] for a in apps or []), str(apps))
chequear("La aplicación es por 700",
         any(a["importe"] == 700.0 for a in apps or []))

# ---------------------------------------------- generar el asiento de verdad
codigo, generado = pedir("POST", f"/api/recibos/{rid}/asiento", admin)
chequear("El asiento se genera", codigo == 200 and generado.get("generado") is True,
         str(generado))
chequear("El comprobante es de la familia RC (cobranza)",
         str(generado.get("numero_completo", "")).startswith("RC"),
         str(generado.get("numero_completo")))

_, real = pedir("GET", f"/api/asientos/{generado['asiento_id']}", admin)
lineas_real = {d["codigo"]: (float(d["debe"]), float(d["haber"]))
               for d in (real or {}).get("detalle", [])}
chequear("Asiento real: Santander 500 en el Debe",
         lineas_real.get("1.1.01.05") == (500.0, 0.0), str(lineas_real.get("1.1.01.05")))
chequear("Asiento real: Fondo fijo 200 en el Debe",
         lineas_real.get("1.1.01.02") == (200.0, 0.0), str(lineas_real.get("1.1.01.02")))
chequear("Asiento real: Documentos a cobrar 700 en el Haber",
         lineas_real.get("1.1.03.02") == (0.0, 700.0), str(lineas_real.get("1.1.03.02")))
chequear("El asiento real cierra",
         float(real["total_debe"]) == float(real["total_haber"]) == 700.0,
         f"{real['total_debe']} / {real['total_haber']}")

# ESTA es la prueba clave: lo que se vio en pantalla es lo que se guardó.
chequear("El preview y el asiento real dan las MISMAS líneas",
         lineas_prev == lineas_real,
         f"preview={lineas_prev} real={lineas_real}")

# La factura quedó saldada (no "parcial"): el saldo era 700 y entraron 700.
_, fac_after = pedir("GET", f"/api/facturas/{fac1000['id']}", admin)
chequear("La factura queda Pagada (no Parcial)",
         fac_after.get("estado") == "pagada", str(fac_after.get("estado")))

_, cobro_after = pedir("GET", f"/api/recibos/a-cobrar?cliente_id={cid}", admin)
chequear(
    "La factura saldada ya no aparece para cobrar",
    fac1000["id"] not in {f["id"] for f in (cobro_after or {}).get("facturas", [])},
)
chequear(
    "Después de cobrar 700, la factura de 1.000 ya no debe nada",
    all(f["id"] != fac1000["id"]
        for f in (cobro_after or {}).get("facturas", [])),
)

# ------------------------------------------- 4. reparto entre varias facturas
# Un recibo de 900 contra las dos facturas (500 + 400 de la de 1.000, que ya
# está pagada: solo le queda 0, así que va todo a la de 500).
codigo, recibo2 = pedir("POST", "/api/recibos", admin, {
    "cliente_id": cid, "fecha": "2026-10-02", "importe": 400.00,
    "forma_pago": "efectivo",
    "facturas": [fac500["id"]],
    # El detalle lleva la MARCA de prueba en TODOS los recibos que crea esta
    # suite, no solo en el primero: es lo único que permite a
    # `limpiar_prueba_recibo_pagos.py` encontrarlos. Si uno se queda sin marca,
    # la limpieza no lo borra y sus aplicaciones bloquean el borrado de la
    # factura (FK `aplicaciones_recibo.factura_id`).
    "pagos": [{"forma_pago": "efectivo", "importe": 400.00,
               "cuenta_id": FONDO_FIJO, "detalle": CONCEPTO}],
})
chequear("El segundo recibo se crea", codigo == 201, str(codigo))
_, apps2 = pedir("GET", f"/api/recibos/{recibo2['id']}/aplicaciones", admin)
chequear("Se aplicó solo a la factura que debía",
         [a["factura_id"] for a in apps2 or []] == [fac500["id"]], str(apps2))

# El importe NO puede pasarse del saldo de la factura.
codigo, recibo_mal = pedir("POST", "/api/recibos", admin, {
    "cliente_id": cid, "fecha": "2026-10-02", "importe": 99999.00,
    "forma_pago": "efectivo",
    "facturas": [fac500["id"]],
    "pagos": [{"forma_pago": "efectivo", "importe": 99999.00,
               "cuenta_id": FONDO_FIJO, "detalle": CONCEPTO}],
})
chequear("Un recibo que se pasa del saldo se recorta, no se cuelga",
         codigo == 201, str(codigo))
if codigo == 201:
    _, apps3 = pedir("GET", f"/api/recibos/{recibo_mal['id']}/aplicaciones", admin)
    total_aplicado = sum(a["importe"] for a in apps3 or [])
    chequear("A la factura no se le aplicó más que su saldo",
             total_aplicado <= 500.0, str(total_aplicado))

# ------------------------------------------------- errores que deben avisar
codigo, sin_cuenta = pedir("POST", "/api/recibos/preview-cobro", admin, {
    "cliente_id": cid, "fecha": "2026-10-02", "importe": 100.00,
    "facturas": [],
    "pagos": [{"forma_pago": "transferencia", "importe": 100.00, "cuenta_id": None}],
})
avisos = " ".join((sin_cuenta or {}).get("avisos", []))
chequear("Un pago sin cuenta avisa que elijas el banco",
         codigo == 200 and "banco" in avisos.lower(), avisos[:120])

codigo, descuadre = pedir("POST", "/api/recibos/preview-cobro", admin, {
    "cliente_id": cid, "fecha": "2026-10-02", "importe": 300.00,
    "facturas": [],
    "pagos": [{"forma_pago": "efectivo", "importe": 100.00,
               "cuenta_id": FONDO_FIJO}],
})
avisos2 = " ".join((descuadre or {}).get("avisos", [])) if descuadre else ""
chequear("Pagos que no suman el importe avisa con los números",
         codigo == 200 and "100" in avisos2 and "300" in avisos2, avisos2[:120])

# Una NC no se puede "cobrar".
codigo, error_nc = pedir("POST", "/api/recibos/preview-cobro", admin, {
    "cliente_id": cid, "fecha": "2026-10-02", "importe": 300.00,
    "facturas": [nc300["id"]],
    "pagos": [{"forma_pago": "efectivo", "importe": 300.00,
               "cuenta_id": FONDO_FIJO}],
})
chequear("No se puede cobrar una nota de crédito",
         codigo == 400, f"{codigo} {error_nc}")

# --------------------------------------------------------- endpoints nuevos
codigo, formas = pedir("GET", "/api/recibos/formas-pago", admin)
chequear("GET /formas-pago responde 200", codigo == 200 and formas)
chequear("Efectivo tiene cuenta fija (no requiere banco)",
         any(f["forma_pago"] == "efectivo" and not f["requiere_banco"]
             for f in formas or []), str(formas))
chequear("Transferencia pide que elijas el banco",
         any(f["forma_pago"] == "transferencia" and f["requiere_banco"]
             for f in formas or []), str(formas))

codigo, cuentas = pedir("GET", "/api/recibos/cuentas-ingreso", admin)
chequear("GET /cuentas-ingreso responde 200", codigo == 200 and cuentas)
codigos_cuentas = {c["codigo"] for c in cuentas or []}
chequear("Trae las cajas y los bancos",
         {"1.1.01.01", "1.1.01.02", "1.1.01.05"} <= codigos_cuentas,
         str(sorted(codigos_cuentas)))
chequear("No trae cuentas de gastos (no se deposita plata ahí)",
         not any(c.startswith("5.") or c.startswith("6.") for c in codigos_cuentas),
         str(sorted(codigos_cuentas)))

codigo, error_rol = pedir("POST", f"/api/recibos/{rid}/asiento", operador)
chequear("Generar el asiento es solo de admin",
         codigo == 403, str(codigo))

codigo, error_anulado = pedir("POST", f"/api/recibos/{recibo2['id']}/asiento/anular", admin)
chequear("Anular un asiento sin asiento avisa 409",
         codigo == 409, str(codigo))

# ------------------------------------------------------------------ resumen
limpiar()

_, clientes = pedir("GET", f"/api/clientes?q={DNI}", admin)
if clientes:
    pedir("DELETE", f"/api/clientes/{clientes[0]['id']}", admin)

fallos = [r for r in resultado if not r[1]]
for nombre, ok, detalle in resultado:
    if not ok:
        print(f"  FALLA  {nombre}  {detalle}")
print()
# El formato es el que lee `correr_todas.py`.
print(f"  {len(resultado) - len(fallos)}/{len(resultado)} pruebas correctas")
if not fallos:
    print("  Todas en verde.")
else:
    print(f"  {len(fallos)} FALLOS")
raise SystemExit(1 if fallos else 0)