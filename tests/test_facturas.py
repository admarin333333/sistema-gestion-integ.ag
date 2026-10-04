"""Pruebas de la Fase 3 — backend de facturas (CRUD, roles, Excel)."""

import os
import io
import json
import urllib.error
import urllib.parse
import urllib.request
# La dirección de la API sale de `GC_BASE_URL` para poder correr estas pruebas
# contra la base de PRUEBAS y no contra la del estudio. Si la variable no
# está, usa 8010 como antes: no cambia cómo se corren.

BASE = os.environ.get("GC_BASE_URL", "http://127.0.0.1:8010")
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


def pedir_binario(metodo, ruta, token=None):
    encabezados = {}
    if token:
        encabezados["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(BASE + ruta, headers=encabezados, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


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

# ------------------------------------------------------------ cliente de prueba
cliente_prueba = {
    "tipo_persona": "fisica",
    "nombre": "Prueba",
    "apellido": "Facturas",
    "dni": "39888777",
    "email": "facturas@ejemplo.com",
    "actividad_economica": "servicios",
    "tipo_actividad": "monotributista",
    "condicion_iva": "monotributista",
    "servicios": [1],
}
codigo, cliente = pedir("POST", "/api/clientes", admin, cliente_prueba)
if codigo == 409:  # quedó de una corrida anterior: lo busco
    codigo, existentes = pedir("GET", "/api/clientes?q=39888777", admin)
    cliente = existentes[0] if existentes else None
chequear("Cliente de prueba listo", cliente is not None, str(cliente))
cid = cliente["id"] if cliente else None

# --------------------------------------------------------------------- listado
codigo, lista = pedir("GET", "/api/facturas", admin)
chequear("GET /facturas -> 200", codigo == 200, str(codigo))
chequear("Devuelve una lista", isinstance(lista, list), str(type(lista)))

# ----------------------------------------------------------------------- alta
base = {
    "cliente_id": cid,
    "fecha": "2026-09-15",
    "tipo_comprobante": "factura_b",
    "punto_venta": "1",
    "numero": "42",
    "concepto": "Honorarios de septiembre",
    "importe": 150000.50,
    "fecha_vencimiento": "2026-10-15",
    "condicion_venta": "cta_corriente_30",
    "cae": "",
    "cae_vencimiento": None,
}
codigo, f1 = pedir("POST", "/api/facturas", admin, base)
chequear("Alta factura -> 201", codigo == 201, str(codigo))
chequear("Punto de venta se rellena a 0001", f1 and f1.get("punto_venta") == "0001", str(f1 and f1.get("punto_venta")))
chequear("Número se rellena a 00000042", f1 and f1.get("numero") == "00000042", str(f1 and f1.get("numero")))
chequear("Arranca en pendiente", f1 and f1.get("estado") == "pendiente", str(f1 and f1.get("estado")))
chequear("Trae el nombre del cliente", f1 and f1.get("cliente_nombre") == "Facturas, Prueba", str(f1 and f1.get("cliente_nombre")))
chequear("CAE vacío se guarda en null", f1 and f1.get("cae") is None, str(f1 and f1.get("cae")))

codigo, repetida = pedir("POST", "/api/facturas", admin, base)
chequear("Mismo tipo+PV+número -> 409", codigo == 409, str(codigo))
chequear("Aviso claro de número repetido", "Factura B 0001-00000042" in str(repetida), str(repetida))

codigo, otra = pedir(
    "POST", "/api/facturas", admin,
    {**base, "numero": "43", "importe": 90000, "condicion_venta": "contado"},
)
chequear("Segunda factura -> 201", codigo == 201, str(codigo))

codigo, tercera = pedir(
    "POST", "/api/clientes", admin,
    {"tipo_persona": "fisica", "nombre": "Prueba2", "apellido": "Facturas",
     "dni": "39888778", "actividad_economica": "comercio",
     "tipo_actividad": "autonomo", "condicion_iva": "responsable_inscripto", "servicios": [1]},
)
otro_cid = tercera.get("id") if tercera else None
codigo, f3 = pedir(
    "POST", "/api/facturas", admin,
    {**base, "cliente_id": otro_cid, "numero": "44", "importe": 60000},
)
chequear("Tercera factura (otro cliente) -> 201", codigo == 201, str(codigo))

# ------------------------------------------------------------ validaciones
malas = [
    ("tipo_comprobante", "factura_z", "comprobante"),
    ("condicion_venta", "tarjeta", "condición"),
    ("punto_venta", "abcdef", "punto de venta"),
    ("numero", "abcdef", "número"),
    ("importe", 0, "importe"),
    ("importe", -5, "importe"),
]
for campo, valor, texto in malas:
    codigo, datos = pedir("POST", "/api/facturas", admin, {**base, **{campo: valor}})
    detalle = str(datos).lower()
    chequear(f"{campo}={valor} rechazado (422)", codigo == 422 and texto in detalle, f"{codigo} {datos}")

codigo, datos = pedir("GET", "/api/facturas?estado=volando", admin)
chequear("Estado inválido -> 400", codigo == 400, str(codigo))

codigo, datos = pedir("GET", "/api/facturas/99999", admin)
chequear("Factura inexistente -> 404", codigo == 404, str(codigo))

# ---------------------------------------------------------------- edición
codigo, editada = pedir("PUT", f"/api/facturas/{f1['id']}", admin, {**base, "importe": 175000})
chequear("Modificar factura -> 200", codigo == 200, str(codigo))
chequear("Se actualizó el importe", editada and float(editada["importe"]) == 175000.0, str(editada and editada.get("importe")))
chequear("Queda marcado actualizado", editada and editada.get("actualizado") is not None)

# ------------------------------------------------------------------ roles
codigo, _ = pedir("POST", "/api/facturas", operador, {**base, "numero": "45"})
chequear("Operador puede crear facturas -> 201", codigo == 201, str(codigo))

codigo, _ = pedir("PUT", f"/api/facturas/{f1['id']}", operador, {**base, "importe": 176000})
chequear("Operador puede modificar -> 200", codigo == 200, str(codigo))

codigo, datos = pedir("POST", f"/api/facturas/{f1['id']}/anular", operador)
chequear("Operador NO puede anular -> 403", codigo == 403, str(codigo))

codigo, datos = pedir("DELETE", f"/api/facturas/{f1['id']}", operador)
chequear("Operador NO puede eliminar -> 403", codigo == 403, str(codigo))

codigo, anulada = pedir("POST", f"/api/facturas/{f1['id']}/anular", admin)
chequear("Admin anula -> estado anulada", codigo == 200 and anulada.get("estado") == "anulada", str(anulada and anulada.get("estado")))

codigo, lista = pedir("GET", "/api/facturas?estado=anulada", admin)
chequear("Filtro por estado funciona", codigo == 200 and any(x["id"] == f1["id"] for x in lista), str(len(lista or [])))

# ------------------------------------------------------------------ totales
codigo, todas = pedir("GET", "/api/facturas", admin)
suma_sin_anuladas = sum(float(x["importe"]) for x in todas if x["estado"] != "anulada")
suma_anuladas = sum(float(x["importe"]) for x in todas if x["estado"] == "anulada")

codigo, t = pedir("GET", "/api/facturas/total", admin)
chequear(
    "El total excluye las anuladas",
    codigo == 200 and abs(float(t["total"]) - suma_sin_anuladas) < 0.01,
    f"total={t.get('total')} esperado={suma_sin_anuladas}",
)

codigo, ta = pedir("GET", "/api/facturas/total?estado=anulada", admin)
chequear(
    "Total filtrado por anuladas si las suma",
    codigo == 200 and abs(float(ta["total"]) - suma_anuladas) < 0.01,
    f"total={ta.get('total')} esperado={suma_anuladas}",
)

codigo, ta_client = pedir("GET", f"/api/facturas/total?cliente_id={cid}", admin)
suma_cliente = sum(
    float(x["importe"]) for x in todas if x["cliente_id"] == cid and x["estado"] != "anulada"
)
chequear(
    "El total respeta el filtro de cliente",
    codigo == 200 and abs(float(ta_client["total"]) - suma_cliente) < 0.01,
    f"total={ta_client.get('total')} esperado={suma_cliente}",
)

codigo, reabierta = pedir("POST", f"/api/facturas/{f1['id']}/reabrir", admin)
chequear("Reabrir -> vuelve a pendiente", reabierta.get("estado") == "pendiente", str(reabierta.get("estado")))

# ------------------------------- una factura con asiento no se puede borrar
# El asiento es un documento contable: si se borrara la factura, el número del
# comprobante quedaría libre y el siguiente reusaría un número ya usado.
codigo, datos = pedir("DELETE", f"/api/facturas/{f1['id']}", admin)
chequear(
    "Factura con asiento NO se borra -> 409",
    codigo == 409,
    str(codigo),
)
chequear(
    "y el aviso dice que hay que anular el asiento",
    "asiento" in str(datos).lower(),
    str(datos)[:160],
)

# ------------------------------------------------------- bloqueo de cliente
codigo, datos = pedir("DELETE", f"/api/clientes/{cid}", admin)
chequear("No se borra el cliente mientras tenga facturas -> 409", codigo == 409, str(codigo))

# --------------------------------------------------------------- filtros
codigo, solo_f1 = pedir("GET", f"/api/facturas?cliente_id={cid}", admin)
chequear(
    "Filtro por cliente",
    codigo == 200 and {x["id"] for x in solo_f1} >= {f1["id"], otra["id"]},
    str([x["id"] for x in (solo_f1 or [])]),
)

codigo, rango = pedir("GET", "/api/facturas?desde=2026-09-01&hasta=2026-09-30", admin)
chequear("Filtro por fechas", codigo == 200 and all("2026-09" in x["fecha"] for x in rango), str(len(rango or [])))

# ------------------------------------------------------------------ Excel
codigo, cabeceras, contenido = pedir_binario(
    "GET", f"/api/facturas/export.xlsx?cliente_id={cid}", admin
)
cabeceras = {k.lower(): v for k, v in cabeceras.items()}
chequear("Export -> 200", codigo == 200, str(codigo))
chequear("Es un .xlsx real (zip PK)", contenido[:2] == b"PK", str(contenido[:8]))
chequear(
    "Nombre de archivo con fecha",
    "informe_facturas_" in cabeceras.get("content-disposition", "")
    and cabeceras.get("content-disposition", "").endswith('.xlsx"'),
    cabeceras.get("content-disposition", ""),
)

try:
    from openpyxl import load_workbook

    libro = load_workbook(io.BytesIO(contenido))
    hoja = libro.active
    filas = list(hoja.iter_rows(values_only=True))
    titulo_excel = filas[0]
    encabezado = filas[2]
    total_excel = filas[-1][6]
    suma_esperada = sum(
        float(x["importe"]) for x in (solo_f1 or []) if x["estado"] != "anulada"
    )
    chequear(
        "Encabezado = ESTUDIO INTEGRAL AM",
        titulo_excel[0] == "ESTUDIO INTEGRAL AM",
        str(titulo_excel[:2]),
    )
    chequear("Encabezado con TOTAL", encabezado[6] == "Importe", str(encabezado[:7]))
    chequear(
        "El total del Excel = suma de importes",
        abs(float(total_excel) - suma_esperada) < 0.01,
        f"excel={total_excel} esperado={suma_esperada}",
    )
    # titulo + fila en blanco + nombres de columna + datos + blanca + TOTAL
    chequear("Una fila por factura", len(filas) == len(solo_f1) + 5, f"{len(filas)} filas / {len(solo_f1)} facturas")
except Exception as exc:  # noqa: BLE001
    chequear("Abrir el Excel", False, str(exc))

# --------------------------------------------------------------------- PDF
codigo, cab, bytes_pdf = pedir_binario("GET", f"/api/facturas/{f1['id']}/pdf", admin)
chequear("Bajar el PDF -> 200", codigo == 200, str(codigo))
# los headers llegan en minúsculas (uvicorn), así que los buscamos sin importar
bajada = {k.lower(): v for k, v in cab.items()}
chequear(
    "Baja como application/pdf y con nombre de archivo",
    bajada.get("content-type") == "application/pdf"
    and "comprobante.pdf" in bajada.get("content-disposition", ""),
    f'{bajada.get("content-type")} / {bajada.get("content-disposition")}',
)
chequear("Es un PDF de verdad (cabecera %PDF)", bytes_pdf[:5] == b"%PDF-", repr(bytes_pdf[:8]))
chequear("El PDF trae contenido", len(bytes_pdf) > 1000, str(len(bytes_pdf)))

codigo, _, _ = pedir_binario("GET", f"/api/facturas/{f1['id']}/pdf", operador)
chequear("El operador también puede bajar el PDF", codigo == 200, str(codigo))

codigo, _, _ = pedir_binario("GET", f"/api/facturas/{f1['id']}/pdf", None)
chequear("Sin token -> 401 en el PDF", codigo == 401, str(codigo))

codigo, _, _ = pedir_binario("GET", "/api/facturas/999999/pdf", admin)
chequear("PDF de una factura que no existe -> 404", codigo == 404, str(codigo))

# -------------------------------------------------------------- limpieza
codigo, _cab, datos = pedir_binario("GET", "/api/facturas/export.xlsx", None)
chequear("Sin token -> 401 en el Excel", codigo == 401, str(codigo))

# Ojo: desde el 02/10/2026 toda factura genera su asiento al darla de alta, y
# **una factura con asiento no se borra por la API** (409 a propósito: el
# asiento es un documento contable y no se puede borrar). Por eso la limpieza
# de este test va por SQL, borrando el asiento primero y después la factura.
# El 409 del DELETE por API se prueba más abajo, en "no se borra con asiento".
import sys as _sys
import os as _os

_sys.path.insert(0, _os.path.join(
    _os.path.dirname(_os.path.abspath(__file__)), "..", "backend"))
from sqlalchemy import text as _text  # noqa: E402
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

from app.database import SessionLocal as _SL  # noqa: E402
import borrar_prueba  # noqa: E402

_db = _SL()
# Solo los asientos de las facturas de los clientes DE PRUEBA. La línea de abajo
# decía `DELETE FROM asientos` a secas, que se llevaba también los asientos
# reales del contador en cada corrida. Ver `borrar_prueba.py`.
_clientes_prueba = [str(cid)] + ([str(otro_cid)] if otro_cid else [])
_marcas = ",".join(_clientes_prueba)
_facturas_prueba = [
    r[0] for r in _db.execute(
        _text(f"SELECT id FROM facturas WHERE cliente_id IN ({_marcas})")
    ).all()
]
borrar_prueba.limpiar_asientos(_db, _facturas_prueba)
borrar_prueba.limpiar_comprobantes(_db)
if _facturas_prueba:
    _fm = ",".join(str(i) for i in _facturas_prueba)
    _db.execute(_text(f"DELETE FROM facturas WHERE id IN ({_fm})"))
_db.commit()
_db.close()

codigo, lista = pedir("GET", f"/api/facturas?cliente_id={cid}", admin)
chequear("Se borraron las facturas de prueba", codigo == 200 and lista == [], str(lista))

codigo, datos = pedir("DELETE", f"/api/clientes/{cid}", admin)
chequear("Ahora sí se borra el cliente de prueba", codigo in (200, 204), str(codigo))
if otro_cid:
    pedir("DELETE", f"/api/clientes/{otro_cid}", admin)

# ------------------------------------------------------------------ reporte
fallidos = [r for r in resultado if not r[1]]
for nombre, ok, detalle in resultado:
    print(f"  {'OK  ' if ok else 'FALLA'} {nombre}" + (f"  -> {detalle}" if not ok else ""))
print(f"\n{len(resultado) - len(fallidos)}/{len(resultado)} pruebas correctas.")
raise SystemExit(1 if fallidos else 0)
