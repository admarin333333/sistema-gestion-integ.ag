import json, urllib.request

BASE = "http://127.0.0.1:8010"
r = urllib.request.Request(BASE + "/api/auth/login", method="POST")
r.add_header("Content-Type", "application/json")
tok = json.loads(urllib.request.urlopen(r, json.dumps({"usuario": "admin", "password": "admin123"}).encode()).read())["access_token"]

# Probar buscar proveedores
c = json.loads(urllib.request.urlopen(urllib.request.Request(BASE + "/api/clientes", headers={"Authorization": "Bearer " + tok})).read())
proveedores = [cli for cli in c if cli.get("tipo") == "proveedor"]
print(f"Total proveedores: {len(proveedores)}")
for p in proveedores[:5]:
    print(f"  id={p['id']} nombre={p['nombre']} cuit={p.get('cuit')}")