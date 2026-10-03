import json, urllib.request

BASE = "http://127.0.0.1:8010"
r = urllib.request.Request(BASE + "/api/auth/login", method="POST")
r.add_header("Content-Type", "application/json")
tok = json.loads(urllib.request.urlopen(r, json.dumps({"usuario": "admin", "password": "admin123"}).encode()).read())["access_token"]
c = json.loads(urllib.request.urlopen(urllib.request.Request(BASE + "/api/clientes", headers={"Authorization": "Bearer " + tok})).read())
for cli in c:
    print(f"id={cli['id']} nombre={cli['nombre']} cuit={cli.get('cuit')} dni={cli.get('dni')} tipo={cli['tipo_persona']}")