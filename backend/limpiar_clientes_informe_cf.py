"""Busca y borra los clientes que dejaron los tests de informe de claves fiscales.

Estos son datos de prueba, no del usuario: los nombres llevan "INFORME CF".
"""

import requests

BASE = "http://127.0.0.1:8010/api"
tok = requests.post(
    f"{BASE}/auth/login", json={"usuario": "admin", "password": "admin123"}
).json()["access_token"]
H = {"Authorization": f"Bearer {tok}"}

r = requests.get(f"{BASE}/clientes?limit=500", headers=H)
datos = r.json()
print("Respuesta de /clientes:", type(datos).__name__, list(datos)[:6] if isinstance(datos, dict) else len(datos))

lista = datos["items"] if isinstance(datos, dict) and "items" in datos else datos
borrados = 0
for c in lista:
    nombre = f"{c.get('apellido') or ''} {c.get('nombre') or ''}"
    if "INFORME CF" in nombre.upper():
        d = requests.delete(f"{BASE}/clientes/{c['id']}", headers=H)
        print(f"  borrado {nombre} (id {c['id']}) -> {d.status_code}")
        borrados += 1

print(f"\nBorrados {borrados} clientes de prueba")