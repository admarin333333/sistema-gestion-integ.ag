"""Listados de anticipos: encabezado ESTUDIO INTEGRAL AM, nombres de
columnas y total abajo, tanto en Excel como en PDF. Tambien el de facturas."""
import json
import urllib.request
import urllib.error
from pathlib import Path

BASE = "http://127.0.0.1:8010/api"
TEMP = Path(r"C:\Users\admar\AppData\Local\Temp\opencode")

resultado = []


def chequear(nombre, ok, detalle=""):
    resultado.append((nombre, bool(ok), detalle))


def pedir(metodo, ruta, token=None, cuerpo=None):
    url = BASE + ruta
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    encabezados = {"Content-Type": "application/json"}
    if token:
        encabezados["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=datos, headers=encabezados, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            crudo = resp.read()
            codigo = resp.status
            tipo = resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        crudo = e.read()
        codigo = e.code
        tipo = e.headers.get("Content-Type", "")
    if "json" in tipo:
        return codigo, json.loads(crudo) if crudo else None
    return codigo, crudo


def login(usuario, clave):
    codigo, datos = pedir("POST", "/auth/login", cuerpo={"usuario": usuario, "password": clave})
    assert codigo == 200, f"login {usuario} -> {codigo}"
    return datos["access_token"]


admin = login("admin", "admin123")

# ------------------------------------------------------------- limpieza previa
codigo, clientes = pedir("GET", "/clientes?q=30111222", admin)
for c in clientes or []:
    _, lista = pedir("GET", f"/anticipos?cliente_id={c['id']}", admin)
    for a in lista or []:
        pedir("DELETE", f"/anticipos/{a['id']}", admin)
    pedir("DELETE", f"/clientes/{c['id']}", admin)

# --------------------------------------------------------------- crear datos
codigo, cliente = pedir("POST", "/clientes", admin, {
    "apellido": "Informe", "nombre": "Prueba",
    "dni": "30111222", "tipo_persona": "fisica",
    "email": "informe@test.com",
    "actividad_economica": "profesional", "tipo_actividad": "monotributista",
    # `condicion_iva` es obligatoria desde el alta del módulo (ver §4.2).
    "condicion_iva": "monotributista",
})
chequear("Cliente de prueba -> 201", codigo == 201, str(codigo))
cid = cliente["id"]

esperado_total = 0.0
creados = []
# El número del anticipo lo genera el backend: no se manda.
for etiqueta, fecha, importe in [
    ("1", "2026-08-20", 30000.00),
    ("2", "2026-09-05", 60000.00),
    ("3", "2026-09-15", 125000.50),
]:
    codigo, anticipo = pedir("POST", "/anticipos", admin, {
        "cliente_id": cid, "fecha": fecha, "importe": importe,
    })
    chequear(f"Alta anticipo {etiqueta} -> 201", codigo == 201, str(codigo))
    creados.append(anticipo)
    esperado_total += importe

# el primero lo dejamos ELIMINADO, para ver que la etiqueta se muestra
codigo, _ = pedir("DELETE", f"/anticipos/{creados[0]['id']}", admin)
chequear("Se elimina el anticipo 1 -> 204", codigo == 204, str(codigo))

# ----------------------------------------------------------------- SIN token
codigo, _ = pedir("GET", "/anticipos/informe.xlsx")
chequear("Excel sin token -> 401", codigo == 401, str(codigo))
codigo, _ = pedir("GET", "/anticipos/informe.pdf")
chequear("PDF sin token -> 401", codigo == 401, str(codigo))

# -------------------------------------------------------------------- EXCEL
codigo, contenido = pedir("GET", f"/anticipos/informe.pdf?cliente_id={cid}", admin)
chequear("PDF -> 200", codigo == 200, str(codigo))
chequear("PDF es un PDF de verdad", isinstance(contenido, bytes)
         and contenido.startswith(b"%PDF"), str(contenido)[:40])
ruta_pdf = TEMP / "informe_anticipos.pdf"
ruta_pdf.write_bytes(contenido)

codigo, contenido = pedir("GET", f"/anticipos/informe.xlsx?cliente_id={cid}", admin)
chequear("Excel -> 200", codigo == 200, str(codigo))
ruta_xlsx = TEMP / "informe_anticipos.xlsx"
ruta_xlsx.write_bytes(contenido)

from openpyxl import load_workbook  # noqa: E402

hoja = load_workbook(ruta_xlsx).active
filas = [[c.value for c in f] for f in hoja.iter_rows()]

chequear("Encabezado 1 = ESTUDIO INTEGRAL AM",
         filas[0][0] == "ESTUDIO INTEGRAL AM", str(filas[0]))
chequear("Fila 2 en blanco", filas[1][0] is None, str(filas[1]))
chequear("Fila 3 = nombres de columna",
         filas[2][:5] == ["Fecha", "Número", "Cliente", "Importe", "Estado"],
         str(filas[2]))
chequear("3 renglones de datos", len(filas) == 8, str(len(filas)))
chequear("Fila de datos 1", filas[3][0] == "2026-09-15" and filas[3][3] == 125000.5,
         str(filas[3]))
chequear("Estado Eliminado visible",
         any(f[4] == "Eliminado" for f in filas[3:6]),
         str([f[4] for f in filas[3:6]]))
chequear("TOTAL abajo del listado", filas[7][2] == "TOTAL", str(filas[7]))
chequear("El total coincide con la suma de la columna",
         abs((filas[7][3] or 0) - esperado_total) < 0.005,
         f"{filas[7][3]} vs {esperado_total}")
suma_columna = sum(f[3] for f in filas[3:6] if isinstance(f[3], (int, float)))
chequear("El total es la suma de los renglones",
         abs(suma_columna - (filas[7][3] or 0)) < 0.005,
         f"{suma_columna} vs {filas[7][3]}")

# ------------------------------------------------------------------ FILTROS
codigo, contenido = pedir(
    "GET", f"/anticipos/informe.xlsx?cliente_id={cid}&desde=2026-09-01&hasta=2026-09-30",
    admin)
hoja2 = load_workbook(__import__("io").BytesIO(contenido)).active
filas2 = [[c.value for c in f] for f in hoja2.iter_rows()]
chequear("Filtro por mes -> 7 filas (enc + col + 2 datos + total)",
         len(filas2) == 7, str(len(filas2)))
chequear("Total filtrado por mes = 185000.50",
         filas2[6][2] == "TOTAL" and abs((filas2[6][3] or 0) - 185000.50) < 0.005,
         str(filas2[6]))

# ------------------------------------------------------------ EXCEL facturas
codigo, contenido = pedir("GET", "/facturas/export.xlsx", admin)
chequear("Excel de facturas -> 200", codigo == 200, str(codigo))
from openpyxl import load_workbook as lw  # noqa: E402
import io  # noqa: E402
hoja3 = lw(io.BytesIO(contenido)).active
filas3 = [[c.value for c in f] for f in hoja3.iter_rows()]
chequear("Facturas: encabezado ESTUDIO INTEGRAL AM",
         filas3[0][0] == "ESTUDIO INTEGRAL AM", str(filas3[0]))
chequear("Facturas: nombres de columna en la fila 3",
         filas3[2][0] == "Fecha" and filas3[2][6] == "Importe", str(filas3[2]))

# ------------------------------------------------------------------ limpieza
_, lista = pedir("GET", f"/anticipos?cliente_id={cid}", admin)
for a in lista or []:
    pedir("DELETE", f"/anticipos/{a['id']}", admin)
codigo, _ = pedir("DELETE", f"/clientes/{cid}", admin)
chequear("Se borra el cliente de prueba", codigo in (200, 204), str(codigo))

fallidos = [r for r in resultado if not r[1]]
for nombre, ok, detalle in resultado:
    print(f"  {'OK  ' if ok else 'FALLA'} {nombre}" + (f"  -> {detalle}" if not ok else ""))
print(f"\n{len(resultado) - len(fallidos)}/{len(resultado)} pruebas correctas.")
print(f"PDF guardado en: {ruta_pdf}")
print(f"Excel guardado en: {ruta_xlsx}")
raise SystemExit(1 if fallidos else 0)
