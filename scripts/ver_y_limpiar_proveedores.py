"""AVISO: este script BORRA proveedores de la base REAL.

    NO lo corras sin leer esto.

Qué hace, en dos pasos:

  1. Lista todos los proveedores (solo lectura, esto es inofensivo).
  2. Borra por API los que tengan "PRUEBA" en el nombre o el apellido.

Contra qué base: `http://127.0.0.1:8010` — la API del programa real, la que
apunta a `gestion_contable`, la del estudio.

Contra la base de pruebas es inofensivo. Contra la real borra cualquier
proveedor cuyo nombre contenga la palabra PRUEBA, sin preguntar.

Lo bueno: la API no borra un proveedor que tenga compras o pagos asociados, así
que los proveedores con movimiento quedan protegidos. Los que no tienen nada
associated, se van.

Cómo se vuelve seguro: cambiar la línea B por `B = "http://127.0.0.1:8011"`.

Por qué sigue acá: quedó del 01/10/2026, cuando se separa clientes de
proveedores y quedaron proveedores de prueba. La separación ya está hecha (ver
`migrar_personas.py` en `backend/migraciones_viejas/`). Se puede borrar sin
consecuencia: Git conserva el historial.
"""

import json
import urllib.request

B = "http://127.0.0.1:8010"
print("ADVERTENCIA: vas a borrar proveedores de la base REAL")
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
