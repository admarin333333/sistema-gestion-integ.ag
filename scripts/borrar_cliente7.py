"""AVISO: este script BORRA un cliente de la base REAL.

    NO lo corras sin leer esto.

Qué hace: `DELETE /api/clientes/7` contra `http://127.0.0.1:8010`, que es la API
del programa real, apuntando a la base `gestion_contable` — la del estudio.

El cliente 7 se llamaba "Juan" y era un cliente REAL. Si el script corre y el
cliente 7 todavía existe, lo borra junto con sus facturas y sus movimientos.

Cómo se vuelve seguro:

  - apuntando a la API de pruebas (puerto 8011), con
    `gestion_contable_test`: cambiar la línea BASE por
    `BASE = "http://127.0.0.1:8011"`;
  - con un respaldo antes (ver `tests/respaldar_todo.py`).

Por qué sigue acá: quedó del 01/10/2026, cuando se estaba reparando la base. No
lo usa nada del proyecto y el cambio ya está aplicado. Está solo como
histórico. Si no lo vas a usar nunca, se puede borrar sin problema: Git conserva
el historial.

IMPORTANTE: las suites de prueba que corren hoy (`tests/`) nunca borran datos
reales, y la "huella digital" de `tests/correr_todas.py` avisa si alguna lo hace.
Esto es anterior a esa protección.
"""

import json
import urllib.request

BASE = "http://127.0.0.1:8010"
r = urllib.request.Request(BASE + "/api/auth/login", method="POST")
r.add_header("Content-Type", "application/json")
tok = json.loads(urllib.request.urlopen(r, json.dumps({"usuario": "admin", "password": "admin123"}).encode()).read())["access_token"]

# Borrar cliente 7 (Juan, id=7, sin ejercicios)
req = urllib.request.Request(BASE + "/api/clientes/7", method="DELETE")
req.add_header("Authorization", "Bearer " + tok)
