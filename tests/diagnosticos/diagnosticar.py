import json, urllib.request

BASE = "http://127.0.0.1:8010"
r = urllib.request.Request(BASE + "/api/auth/login", method="POST")
r.add_header("Content-Type", "application/json")
tok = json.loads(urllib.request.urlopen(r, json.dumps({"usuario": "admin", "password": "admin123"}).encode()).read())["access_token"]

# Ver ejercicio 2
e = json.loads(urllib.request.urlopen(urllib.request.Request(BASE + "/api/balance-rt54/ejercicios/2", headers={"Authorization": "Bearer " + tok})).read())

# Mostrar TODOS los rubros del ESP con sus valores actual
activo = e.get("esp", {}).get("activo", [])
print("=== ESP ACTIVO - todos los rubros ===")
for item in activo:
    actual = item.get("actual", 0)
    anterior = item.get("anterior", 0)
    print(f"  {item['clave']} ({item['tipo']}): actual={actual}, anterior={anterior}")

# Mostrar ER
er = e.get("er", [])
print("\n=== ER - rubros con actual != 0 ===")
for item in er:
    if item.get("actual") not in (0, None, ""):
        print(f"  {item['clave']} ({item['tipo']}): actual={item['actual']}")

# Mostrar EEPN
eepn = e.get("eepn", {})
print(f"\n=== EEPN - filas: {len(eepn.get('filas', []))} ===")
for f in eepn.get("filas", [])[:3]:
    print(f"  Fila: {f}")