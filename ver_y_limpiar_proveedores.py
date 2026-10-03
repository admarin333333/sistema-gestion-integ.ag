import json
import urllib.request

B = "http://127.0.0.1:8010"
r = urllib.request.Request(B + "/api/auth/login", method="POST")
r.add_header("Content-Type", "application/json")
tok = json.loads(
    urllib.request.urlopen(r, json.dumps({"usuario": "admin", "password": "admin123"}).encode()).read()
)["access_token"]
H = {"Authorization": "Bearer " + tok}

p = json.loads(urllib.request.urlopen(urllib.request.Request(B + "/api/proveedores", headers=H)).read())
print("proveedores:", len(p))
for x in p:
    print("  cuenta", x["nro_cuenta"], "|", x["nombre_completo"], "| dni", x["dni"])

for x in p:
    if "PRUEBA" in ((x.get("nombre") or "") + (x.get("apellido") or "")):
        req = urllib.request.Request(B + f"/api/proveedores/{x['id']}", method="DELETE")
        req.add_header("Authorization", "Bearer " + tok)
        urllib.request.urlopen(req)
        print("borrado el de prueba:", x["nombre_completo"])