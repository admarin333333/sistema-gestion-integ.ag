import json, urllib.request

BASE = "http://127.0.0.1:8010"
r = urllib.request.Request(BASE + "/api/auth/login", method="POST")
r.add_header("Content-Type", "application/json")
tok = json.loads(urllib.request.urlopen(r, json.dumps({"usuario": "admin", "password": "admin123"}).encode()).read())["access_token"]

# Ver ejercicio 2 (el que tenía los datos antes)
e = json.loads(urllib.request.urlopen(urllib.request.Request(BASE + "/api/balance-rt54/ejercicios/2", headers={"Authorization": "Bearer " + tok})).read())

# Mostrar totales y valores clave
c = e.get('cabecera', {})
print("=== CABECERA ===")
for k, v in c.items():
    if v not in (None, '', 0) and k not in ('id', 'cliente_id', 'fecha_inicio', 'fecha_fin', 'nombre'):
        print(f"  {k}: {v}")

print("\n=== ESP ACTIVO - total ===")
activo = e.get("esp", {}).get("activo", [])
for item in activo:
    if item.get("tipo") in ("rubro", "total") and item.get("actual") not in (0, None, ""):
        print(f"  {item['clave']} ({item['tipo']}): actual={item['actual']}, anterior={item.get('anterior')}")

print("\n=== ER - total ===")
er = e.get("er", [])
for item in er:
    if item.get("tipo") in ("rubro", "total") and item.get("actual") not in (0, None, ""):
        print(f"  {item['clave']} ({item['tipo']}): actual={item['actual']}")

print("\n=== EEPN ===")
eepn = e.get("eepn", {})
print(f"Filas: {len(eepn.get('filas', []))}")
for f in eepn.get("filas", [])[:3]:
    print(f"  Fila: clave={f.get('clave')}, celdas keys: {list(f.get('celdas', {}).keys())[:5]}")