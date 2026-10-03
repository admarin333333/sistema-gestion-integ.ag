import json, urllib.request, openpyxl, io

BASE = "http://127.0.0.1:8010"
r = urllib.request.Request(BASE + "/api/auth/login", method="POST")
r.add_header("Content-Type", "application/json")
tok = json.loads(urllib.request.urlopen(r, json.dumps({"usuario": "admin", "password": "admin123"}).encode()).read())["access_token"]

# Download Excel
url = BASE + "/api/balance-rt54/ejercicios/2/moneda-homogenea.xlsx"
req = urllib.request.Request(url, headers={"Authorization": "Bearer " + tok})
resp = urllib.request.urlopen(req)
datos = resp.read()

wb = openpyxl.load_workbook(io.BytesIO(datos), data_only=True)
ws = wb.active

print("=== HOJA:", ws.title == "")
print("A1:", ws["A1"].value)
print("A3:", ws["A3"].value)
print("A4:", ws["A4"].value)
print("A5:", ws["A5"].value)
print("B6:", ws["B6"].value, "formato:", ws["B6"].number_format)
print("C8:", ws.cell(row=8, column=8).value)

print("\n=== NUEVA SECCION (filas 8-10) ===")
for row in range(8, 11):
    a = ws.cell(row=row, column=1).value
    b = ws.cell(row=row, column=2).value
    c = ws.cell(row=row, column=3).value
    print("  Fila %d: A=%s B=%s C=%s" % (row, str(a)[:30] if a else "None", str(b)[:30] if b else "None", str(c)[:30] if c else "None"))

print("\n=== TABLAS PRINCIPALES ===")
# Mostrar los primeros renglones de cada tabla
for section_title, start_row in [("ACTIVO", 9), ("PASIVO", 20), ("RESULTADOS", 31)]:
    print("--- %s (empieza fila %d) ---" % (section_title, start_row))
    for row in range(start_row, start_row + 6):
        rubro = ws.cell(row=row, column=1).value
        saldo = ws.cell(row=row, column=2).value
        actual = ws.cell(row=row, column=3).value
        if rubro:
            print("  %s | Saldo=%s | Act=%s" % (str(rubro)[:40], str(saldo)[:20] if saldo else "None", str(actual)[:20] if actual else "None"))