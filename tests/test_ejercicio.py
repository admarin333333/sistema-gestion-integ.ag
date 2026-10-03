"""El ejercicio contable del ESTUDIO y la numeración por ejercicio.

    python -X utf8 test_ejercicio.py

Lo que se comprueba:
  1. El ejercicio 2026/2027 (01/09/2026 a 31/08/2027) está abierto.
  2. La numeración **NO se parte el 1 de enero**: dentro del mismo ejercicio el
     número corre corrido aunque cambie el año.
  3. Al abrir el ejercicio siguiente, el número vuelve a 000001.
  4. Una fecha fuera de todo ejercicio habilitado no crea comprobante y avisa.
  5. Un ejercicio cerrado no recibe asientos.
  6. No se confunde con el ejercicio de los CLIENTES (que va aparte).
"""

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date

BASE = "http://127.0.0.1:8010"
ok = 0
fallos = []
_RUTA_BACKEND = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
)
sys.path.insert(0, _RUTA_BACKEND)


def req(metodo, ruta, datos=None, token=None):
    r = urllib.request.Request(BASE + ruta, method=metodo)
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", "Bearer " + token)
    cuerpo = json.dumps(datos).encode() if datos is not None else None
    try:
        with urllib.request.urlopen(r, cuerpo, timeout=30) as resp:
            t = resp.read().decode()
            return resp.status, json.loads(t) if t else None
    except urllib.error.HTTPError as e:
        t = e.read().decode() or "{}"
        try:
            return e.code, json.loads(t)
        except json.JSONDecodeError:
            return e.code, {"detail": t}


def check(nombre, cond, detalle=""):
    global ok
    if cond:
        ok += 1
        print(f"  OK  {nombre}")
    else:
        fallos.append(nombre)
        print(f"FALLA {nombre} -> {detalle}")


def borrar_ejercicio_de_prueba(db):
    """Borra el ejercicio "PRUEBA %" y todo lo que cuelga de él.

    El orden lo mandan las FK y es lo que cuesta acordarse:
    `asiento_detalle` → `asiento_origen` → `asientos` → `comprobantes_internos`
    → `periodos` → `ejercicios`. Al revés, MySQL corta con "Cannot delete or
    update a parent row" y la suite se muere antes de medir nada.
    """
    cond = "SELECT id_ejercicio FROM ejercicios WHERE nombre LIKE 'PRUEBA%'"
    comprobantes = f"SELECT id_comprobante FROM comprobantes_internos WHERE id_ejercicio IN ({cond})"
    asientos = f"SELECT id_asiento FROM asientos WHERE id_comprobante IN ({comprobantes})"

    db.execute(text(f"DELETE FROM asiento_origen WHERE id_asiento IN ({asientos})"))
    db.execute(text(f"DELETE FROM asiento_detalle WHERE id_asiento IN ({asientos})"))
    db.execute(text(f"DELETE FROM asientos WHERE id_comprobante IN ({comprobantes})"))
    db.execute(text(f"DELETE FROM comprobantes_internos WHERE id_ejercicio IN ({cond})"))
    db.execute(text(f"DELETE FROM periodos WHERE id_ejercicio IN ({cond})"))
    db.execute(text("DELETE FROM ejercicios WHERE nombre LIKE 'PRUEBA%'"))


def borrar_pruebas_sql(db):
    """Borra los asientos y comprobantes DE PRUEBA, y solo esos.

    Se eligen por el concepto: todo lo que dice "PRUEBA" adentro. Un `DELETE
    FROM asientos` a secas se lleva los asientos reales del estudio y no hay
    forma de recuperarlos — esa fue la razón de que esta función exista.

    Va por SQL y no por la API a propósito: la API, bien hecha, no borra un
    asiento contabilizado. Acá hay que limpiar igual para que la suite sea
    reentrante, y hacerlo por SQL es lo único que alcanza.
    """
    pruebas = db.execute(
        text("SELECT id_asiento FROM asientos WHERE concepto LIKE '%PRUEBA%'")
    ).fetchall()
    for (aid,) in pruebas:
        db.execute(text("DELETE FROM asiento_origen WHERE id_asiento = :a"), {"a": aid})
        db.execute(text("DELETE FROM asiento_detalle WHERE id_asiento = :a"), {"a": aid})
        db.execute(text("DELETE FROM asientos WHERE id_asiento = :a"), {"a": aid})
    db.execute(
        text("DELETE FROM comprobantes_internos WHERE concepto LIKE '%PRUEBA%'")
    )


st, tok = req("POST", "/api/auth/login", {"usuario": "admin", "password": "admin123"})
token = tok.get("access_token")
check("login", st == 200 and token, str(st))

from sqlalchemy import text  # noqa: E402
from app.database import SessionLocal  # noqa: E402

_db = SessionLocal()
# Los asientos de prueba se borran al principio y al final para no ensuciar.

# OJO: acá se borra SOLO lo que dice "PRUEBA" en el concepto. Antes la suite
# hacía `DELETE FROM asientos` a secas, que se llevaba los asientos REALES del
# estudio cada vez que se corría: no había forma de recuperarlos. Un test no
# puede borrar lo que el contador cargó.
borrar_pruebas_sql(_db)

# También el ejercicio de prueba de la corrida anterior. Antes solo se borraba
# al final, así que una corrida interrupted dejaba el "PRUEBA 2025/2026" y la
# siguiente fallaba con "Ya existe un ejercicio llamado".
borrar_ejercicio_de_prueba(_db)
_db.commit()
_db.close()

# El ejercicio de prueba: uno cerrado del año pasado.
st, r = req("POST", "/api/ejercicios", {
    "nombre": "PRUEBA 2025/2026",
    "fecha_inicio": "2025-09-01", "fecha_fin": "2026-08-31",
    "cerrado": False,
}, token)
check("crea un ejercicio de prueba", st == 201, f"{st} {str(r)[:130]}")
PRUEBA_ID = r["id_ejercicio"]

print("\n== El ejercicio del estudio ==")
st, r = req("GET", "/api/ejercicios", token=token)
ej = next((e for e in r["ejercicios"] if e["nombre"] == "2026/2027"), None)
check("está cargado el 2026/2027", ej is not None, str(r)[:200])
check("empieza el 01/09/2026", ej and ej["fecha_inicio"] == "2026-09-01",
      str(ej and ej["fecha_inicio"]))
check("termina el 31/08/2027", ej and ej["fecha_fin"] == "2027-08-31",
      str(ej and ej["fecha_fin"]))
check("está ABIERTO (recibe asientos)", ej and ej["cerrado"] is False,
      str(ej and ej["cerrado"]))
check("y es el de hoy", ej and ej["es_el_de_hoy"] is True,
      f"hoy={date.today()} es_el_de_hoy={ej and ej['es_el_de_hoy']}")

st, r = req("GET", "/api/ejercicios/vigente", token=token)
check("el endpoint vigente devuelve el mismo",
      r["ejercicio"] and r["ejercicio"]["nombre"] == "2026/2027", str(r)[:150])

print("\n== La numeración NO se parte el 1 de enero ==")
st, c1 = req("POST", "/api/comprobantes-internos", {
    "codigo_comprobante": "OP", "fecha": "2026-12-30", "concepto": "PRUEBA Dic 2026",
}, token)
check("crea el comprobante de diciembre", st == 201, f"{st} {str(c1)[:120]}")
st, c2 = req("POST", "/api/comprobantes-internos", {
    "codigo_comprobante": "OP", "fecha": "2027-01-05", "concepto": "PRUEBA Enero 2027",
}, token)
check("crea el de enero del año siguiente", st == 201, f"{st} {str(c2)[:120]}")
# Lo importante: diciembre es 2026 y enero es 2027 (año distinto), pero los dos
# están en el MISMO ejercicio, así que el número sigue y no vuelve a 1.
check("diciembre 2026 y enero 2027 están en el mismo ejercicio",
      c1["anio"] == 2026 and c2["anio"] == 2027, f"{c1['anio']} / {c2['anio']}")
check("el número SIGUE (no se reinicia el 1 de enero)",
      c2["numero"] == c1["numero"] + 1,
      f"{c1['numero_completo']} vs {c2['numero_completo']}")

print("\n== Al abrir el ejercicio siguiente, vuelve a 000001 ==")
st, sig = req("POST", "/api/ejercicios", {
    "nombre": "PRUEBA 2027/2028",
    "fecha_inicio": "2027-09-01", "fecha_fin": "2028-08-31",
    "cerrado": False,
}, token)
check("crea el ejercicio siguiente", st == 201, f"{st} {str(sig)[:120]}")
SIG_ID = sig["id_ejercicio"]
st, c3 = req("POST", "/api/comprobantes-internos", {
    "codigo_comprobante": "OP", "fecha": "2027-09-02", "concepto": "PRUEBA Sep 2027",
}, token)
check("el primer comprobante del ejercicio nuevo es 000001",
      st == 201 and c3["numero"] == 1, f"{st} {c3.get('numero_completo')}")

print("\n== Fecha fuera de todo ejercicio habilitado ==")
st, r = req("POST", "/api/comprobantes-internos", {
    "codigo_comprobante": "OP", "fecha": "2029-05-10", "concepto": "Lejos",
}, token)
# 409 y no 400: desde que existen los PERÍODOS (02/10/2026), "no se puede
# trabajar en esta fecha" es un conflicto de negocio — está el ejercicio o el
# mes cerrado — y no un dato mal cargado. Los dos casos van 409 para que el
# frontend sepa que es lo mismo y muestre el mismo cartel.
check("NO crea el comprobante", st == 409, f"{st} {str(r)[:130]}")
check("y explica por qué", "fuera de todo ejercicio" in str(r.get("detail", "")),
      str(r.get("detail"))[:180])

print("\n== Ejercicio cerrado no recibe asientos ==")
st, r = req("POST", f"/api/ejercicios/{PRUEBA_ID}/cerrar", token=token)
check("cierra el ejercicio de prueba", st == 200 and r["cerrado"] is True,
      f"{st} {str(r)[:120]}")
st, r = req("POST", "/api/comprobantes-internos", {
    "codigo_comprobante": "OP", "fecha": "2026-03-10", "concepto": "En un cerrado",
}, token)
check("NO crea comprobante en un ejercicio cerrado", st == 409,
      f"{st} {str(r)[:130]}")
check("dice que está cerrado", "cerrado" in str(r.get("detail", "")).lower(),
      str(r.get("detail"))[:180])

st, r = req("POST", f"/api/ejercicios/{PRUEBA_ID}/abrir", token=token)
check("se puede reabrir", st == 200 and r["cerrado"] is False, f"{st}")

print("\n== Un ejercicio no puede pisarse con otro ==")
st, r = req("POST", "/api/ejercicios", {
    "nombre": "PRUEBA pise",
    "fecha_inicio": "2026-10-01", "fecha_fin": "2027-03-31",
}, token)
check("rechaza un ejercicio que se superpone", st == 409, f"{st} {str(r)[:130]}")
check("y lo dice", "pisa" in str(r.get("detail", "")).lower(), str(r.get("detail")))

print("\n== El fin no puede ser antes del inicio ==")
st, r = req("POST", "/api/ejercicios", {
    "nombre": "PRUEBA al reves",
    "fecha_inicio": "2026-09-01", "fecha_fin": "2026-08-31",
}, token)
check("rechaza", st == 400, f"{st} {str(r)[:120]}")
check("avisa cuál es el problema", "anterior" in str(r.get("detail", "")),
      str(r.get("detail")))

print("\n== No se mezcla con el ejercicio de los CLIENTES ==")
# El cierre de cada cliente vive en `personas.fecha_cierre_ejercicio` (día y
# mes, que se repiten todos los años). Es un campo DISTINTO al del estudio.
_db = SessionLocal()
con_cliente = _db.execute(
    text("SELECT COUNT(*) FROM personas WHERE fecha_cierre_ejercicio IS NOT NULL")
).scalar()
fechas = [
    str(r[0])
    for r in _db.execute(
        text(
            "SELECT fecha_cierre_ejercicio FROM personas "
            "WHERE fecha_cierre_ejercicio IS NOT NULL"
        )
    )
]
bal = _db.execute(
    text("SELECT COUNT(*) FROM bal_rt54_ejercicios")
).scalar()
_db.close()
check("los clientes tienen su propia fecha de cierre", con_cliente > 0,
      f"{con_cliente} clientes")
print(f"     fechas de cierre de clientes: {', '.join(sorted(set(fechas)))}")
print(f"     fecha de cierre del ESTUDIO:  2027-08-31 (31 de agosto)")
check("las fechas de cierre de los clientes son DISTINTAS a las del estudio",
      "2027-08-31" not in fechas, str(fechas))
check("el ejercicio del cliente es otra tabla (bal_rt54_ejercicios)",
      bal > 0, f"{bal} ejercicios de cliente")

# ------------------------------------------------------------------ limpieza
_db = SessionLocal()
borrar_pruebas_sql(_db)
# El orden lo mandan las FK: los asientos cuelgan del comprobante, el comprobante
# del ejercicio y el período del ejercicio. Al revés, MySQL corta la suite.
borrar_ejercicio_de_prueba(_db)
_db.commit()
_db.close()

print(f"\n{ok} OK / {len(fallos)} fallos")
if fallos:
    raise SystemExit(1)
