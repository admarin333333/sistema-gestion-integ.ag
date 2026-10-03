import json, urllib.request

BASE = "http://127.0.0.1:8010"
r = urllib.request.Request(BASE + "/api/auth/login", method="POST")
r.add_header("Content-Type", "application/json")
tok = json.loads(urllib.request.urlopen(r, json.dumps({"usuario": "admin", "password": "admin123"}).encode()).read())["access_token"]

# Borrar cliente 7 (Juan, id=7, sin ejercicios)
req = urllib.request.Request(BASE + "/api/clientes/7", method="DELETE")
req.add_header("Authorization", "Bearer " + tok)
req.add_header("Content-Type", "application/json")
try:
    resp = urllib.request.urlopen(req)
    print("Borrado cliente 7:", resp.status)
except urllib.error.HTTPError as e:
    print("Error borrando cliente 7:", e.code, e.read().decode()[:200])

# Listar clientes restantes
c = json.loads(urllib.request.urlopen(urllib.request.Request(BASE + "/api/clientes", headers={"Authorization": "Bearer " + tok})).read())
print("\nClientes restantes:")
for cli in c:
    print(f"id={cli['id']} nombre={cli['nombre']} cuit={cli.get('cuit')} dni={cli.get('dni')}")