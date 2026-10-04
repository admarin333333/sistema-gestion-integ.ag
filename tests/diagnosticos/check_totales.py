import json, urllib.request

BASE = "http://127.0.0.1:8010"
r = urllib.request.Request(BASE + "/api/auth/login", method="POST")
r.add_header("Content-Type", "application/json")
tok = json.loads(urllib.request.urlopen(r, json.dumps({"usuario": "admin", "password": "admin123"}).encode()).read())["access_token"]

e = json.loads(urllib.request.urlopen(urllib.request.Request(BASE + "/api/balance-rt54/ejercicios/2", headers={"Authorization": "Bearer " + tok})).read())

# ESP ACTIVO
activo = e.get("esp", {}).get("activo", [])
print("=== ESP ACTIVO ===")
for item in activo:
    if item.get("tipo") in ("rubro", "total") and item.get("actual") not in (0, None, ""):
        print(f'  {item["clave"]} ({item["tipo"]}): actual={item["actual"]}, anterior={item.get("anterior")}')

# ER
er = e.get("er", [])
print("=== ER ===")
for item in er:
    if item.get("tipo") in ("rubro", "total") and item.get("actual") not in (0, None, ""):
        print(f'  {item["clave"]} ({item["tipo"]}): actual={item["actual"]}')

# EEPN
eepn = e.get("eepn", {})
print("EEPN filas:", len(eepn.get("filas", [])))
for f in eepn.get("filas", [])[:3]:
    print(f'  Fila: {f}')
"