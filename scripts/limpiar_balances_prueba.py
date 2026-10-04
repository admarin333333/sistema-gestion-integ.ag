"""AVISO: este script BORRA datos de la base REAL.

    NO lo corras sin leer esto.

Qué hace: recorre TODOS los clientes y borra los ejercicios de balance RT54 cuyo
nombre empieza con "prueba-". O sea, borra balances completos con sus notas y sus
valores.

Contra qué base: `http://127.0.0.1:8010`, que es la API del programa real, la que
apunta a `gestion_contable` — la del estudio.

Contra la base de pruebas (puerto 8011) es inofensivo: ahí los balances que hay
se llaman "2025" y "2026". Pero contra la real borra cualquier balance que
alguien haya mandado a llamar "prueba-", sin preguntar.

Cómo se vuelve seguro: cambiar la línea BASE por
`BASE = "http://127.0.0.1:8011"`.

Por qué sigue acá: quedó del 01/10/2026. Los balances de prueba que dejó ya no
están (verificado: en la base real hay 2 ejercicios, "2025" y "2026", ninguno
empieza con "prueba-"). El trabajo ya está hecho; se puede borrar sin
consecuencia: Git conserva el historial.
"""

import json
import urllib.request

BASE = "http://127.0.0.1:8010"
print("ADVERTENCIA: vas a borrar balances de la base REAL")
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
