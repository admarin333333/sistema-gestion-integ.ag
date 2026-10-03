import json, urllib.request

BASE = "http://127.0.0.1:8010"
r = urllib.request.Request(BASE + "/api/auth/login", method="POST")
r.add_header("Content-Type", "application/json")
tok = json.loads(urllib.request.urlopen(r, json.dumps({"usuario": "admin", "password": "admin123"}).encode()).read())["access_token"]

# Probar búsqueda en clientes
url = BASE + "/api/clientes?search=PROVEEDOR"
req = urllib.request.Request(url, headers={"Authorization": "Bearer " + tok})
try:
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read())
    print(f"Resultados para 'PROVEEDOR': {len(data)}")
    for d in data:
        print(f"  id={d['id']} nombre={d['nombre']} tipo={d['tipo']} cuit={d.get('cuit')}")
except Exception as e:
    print(f"Error: {e.code if hasattr(e, 'code') else 'unknown'}: {e.read().decode()[:200] if hasattr(e, 'read') else e}")