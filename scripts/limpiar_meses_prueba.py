"""AVISO: este script BORRA datos de la base REAL.

    NO lo corras sin leer esto.

Qué hace: borra los vencimientos de los meses cuyo año está en una lista de años
que "nunca son reales" (1999, 2099, 2050) — los que inventaron los tests.

Contra qué base: `http://127.0.0.1:8010/api` — la API del programa real, la que
apunta a `gestion_contable`, la del estudio.

Lo bueno: el filtro es por AÑO, y esos tres años no son plausibles para un
estudio contable, así que no toca los meses reales. Aun así, borra sin preguntar
y sin confirmar.

Contra la base de pruebas es inofensivo.

Cómo se vuelve seguro: cambiar la línea BASE por
`BASE = "http://127.0.0.1:8011/api"`.

Por qué sigue acá: quedó del 01/10/2026. Los meses de prueba que dejó ya no
están (la suite `test_vencimientos.py` limpia lo suyo). Se puede borrar sin
consecuencia: Git conserva el historial.
"""

import requests

BASE = "http://127.0.0.1:8010/api"
print("ADVERTENCIA: vas a borrar meses de vencimientos de la base REAL")

tok = requests.post(
    f"{BASE}/auth/login", json={"usuario": "admin", "password": "admin123"}
).json()["access_token"]
H = {"Authorization": f"Bearer {tok}"}

# Años que NUNCA son reales: los inventaron los tests.
ANIOS_PRUEBA = {1999, 2099, 2050}

meses = requests.get(f"{BASE}/vencimientos-impositivos/meses", headers=H).json()
print("Meses en la base:")
for m in meses:
    print(f"  {m['anio']}-{m['mes']:02d}: {m['cantidad']} vencimientos")

borrados = 0
for m in meses:
    if m["anio"] not in ANIOS_PRUEBA:
        continue
    r = requests.post(
        f"{BASE}/vencimientos-impositivos",
        params={"anio": m["anio"], "mes": m["mes"], "vaciar": "true"},
        json=[],
        headers=H,
    )
    print(f"\n  limpiando {m['anio']}-{m['mes']:02d} -> {r.status_code}")
    borrados += 1

print(f"\n{borrados} meses de prueba limpiados")

print("\nQueda:")
for m in requests.get(f"{BASE}/vencimientos-impositivos/meses", headers=H).json():
    print(f"  {m['anio']}-{m['mes']:02d}: {m['cantidad']} vencimientos")
