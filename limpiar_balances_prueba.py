import json
import urllib.request

BASE = "http://127.0.0.1:8010"
r = urllib.request.Request(BASE + "/api/auth/login", method="POST")
r.add_header("Content-Type", "application/json")
tok = json.loads(urllib.request.urlopen(r, json.dumps({"usuario": "admin", "password": "admin123"}).encode()).read())["access_token"]
H = {"Authorization": "Bearer " + tok}

for c in json.loads(urllib.request.urlopen(urllib.request.Request(BASE + "/api/clientes", headers=H)).read()):
    ejs = json.loads(urllib.request.urlopen(
        urllib.request.Request(BASE + f"/api/balance-rt54/ejercicios?cliente_id={c['id']}", headers=H)).read())
    for e in ejs:
        if e["nombre"].startswith("prueba-"):
            req = urllib.request.Request(BASE + f"/api/balance-rt54/ejercicios/{e['id']}", method="DELETE")
            req.add_header("Authorization", "Bearer " + tok)
            try:
                urllib.request.urlopen(req)
                print("borrado:", c["nombre_completo"], e["nombre"])
            except Exception as ex:
                print("no se pudo borrar:", e["nombre"], ex)
print("limpieza lista")