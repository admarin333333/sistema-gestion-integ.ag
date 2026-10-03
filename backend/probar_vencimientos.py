"""Prueba rápida de los endpoints de Vencimientos (coneptos + meses)."""

import json

import requests

BASE = "http://127.0.0.1:8010/api"
tok = requests.post(
    f"{BASE}/auth/login", json={"usuario": "admin", "password": "admin123"}
).json()["access_token"]
H = {"Authorization": f"Bearer {tok}"}


def ver(titulo, r):
    print(f"\n=== {titulo} -> {r.status_code}")
    try:
        print(json.dumps(r.json(), ensure_ascii=False, indent=2)[:1200])
    except Exception:
        print(r.text[:400])


ver("catalogo de conceptos", requests.get(f"{BASE}/vencimientos-impositivos/conceptos", headers=H))
ver("meses cargados", requests.get(f"{BASE}/vencimientos-impositivos/meses", headers=H))
ver("impuestos (grilla)", requests.get(f"{BASE}/vencimientos-impositivos/impuestos", headers=H))
ver(
    "octubre 2026",
    requests.get(f"{BASE}/vencimientos-impositivos?anio=2026&mes=10", headers=H),
)