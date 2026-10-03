"""Limpia los meses de prueba de Vencimientos (los años raros que usaron los tests).

Borra los vencimientos y el registro del mes. NO toca los meses reales
(2026 y 2027). Ejecutar con:

    python -X utf8 limpiar_meses_prueba.py
"""

import requests

BASE = "http://127.0.0.1:8010/api"
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