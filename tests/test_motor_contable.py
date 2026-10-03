"""Prueba del motor contable: comprobantes, asientos, partida doble y saldos.

Corre contra el backend:  python -X utf8 test_motor_contable.py
"""

import json
import urllib.error
import urllib.request
from datetime import date
import os
import sys

# El backend, calculado desde donde esta este archivo: asi el proyecto
# se puede mover de carpeta sin romper los tests.
_RUTA_BACKEND = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
)
# La carpeta de los tests, para poder importar `borrar_prueba` (el helper que
# sabe qué es dato de prueba y cuál no).
_CARPETA_TESTS = os.path.dirname(os.path.abspath(__file__))

BASE = "http://127.0.0.1:8010"
ok = 0
fallos = []
creados = {"comprobantes": [], "asientos": []}


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
            return e.code, {"detalle": t}


def check(nombre, cond, detalle=""):
    global ok
    if cond:
        ok += 1
        print(f"  OK  {nombre}")
    else:
        fallos.append(nombre)
        print(f"FALLA {nombre} -> {detalle}")


st, tok = req("POST", "/api/auth/login", {"usuario": "admin", "password": "admin123"})
token = tok.get("access_token")
check("login", st == 200 and token, str(st))

# --- limpiar-restos de corridas anteriores ---
# Si el test se cortó a mitad de camino, quedaron asientos sueltos y los saldos
# dan cualquier cosa. Se borran TODOS antes de empezar.
import os as _os  # noqa: E402
import sys as _sys  # noqa: E402

_sys.path.insert(0, _RUTA_BACKEND)
_os.chdir(_RUTA_BACKEND)
_sys.path.insert(0, _CARPETA_TESTS)
import borrar_prueba  # noqa: E402
from sqlalchemy import text as _text  # noqa: E402
from app.database import SessionLocal as _SL  # noqa: E402

# Los conceptos que usa esta suite. Son palabras comunes ("Cobranza", "Pago
# proveedor"), así que solas NO identifican un asiento de prueba: un contador
# podría tener un asiento que se llame igual. Por eso la limpieza de arranque
# además exige que el asiento NO tenga `asiento_origen`: todo asiento que nace
# de una factura, un recibo o una compra lo tiene, y esos son los del contador.
# Los asientos manuales (sin origen) son los que esta suite crea por su cuenta.
# Antes la línea era `DELETE FROM asientos` a secas, que se llevaba los reales.
_CONCEPTOS_MOTOR = (
    "Pago proveedor", "Otro pago", "Cobranza", "Pago de enero",
    "Compra de mercadería", "Prueba reglas", "Borrador que no debe contar",
)

_db = _SL()
# Lo que dejaron las corridas anteriores. Esta suite chequea la NUMERACIÓN
# ("el número arranca en 1"), que es lo único que no se puede medir por
# diferencia: si quedó un comprobante de más, el correlativo arranca en 15 y la
# prueba falla aunque el sistema esté perfecto. Antes no pasaba porque
# `test_ejercicio.py` —que corre antes, por orden alfabético— borraba los
# asientos de todos y de paso tapaba la basura de todo el mundo. Ahora cada suite
# se limpia lo suyo.
borrar_prueba.limpiar_todo(_db)

for _concepto in _CONCEPTOS_MOTOR:
    _db.execute(
        _text(
            "DELETE FROM asiento_detalle WHERE id_asiento IN ("
            "  SELECT id_asiento FROM asientos a WHERE a.concepto = :c"
            "    AND NOT EXISTS (SELECT 1 FROM asiento_origen o "
            "                    WHERE o.id_asiento = a.id_asiento))"
        ),
        {"c": _concepto},
    )
    _db.execute(
        _text(
            "DELETE FROM asientos WHERE concepto = :c AND NOT EXISTS ("
            "  SELECT 1 FROM asiento_origen o WHERE o.id_asiento = asientos.id_asiento)"
        ),
        {"c": _concepto},
    )
# Los comprobantes internos de esta suite son los que su concepto está en la
# misma lista. Los del contador (FV-000008, FP-000001...) no se tocan.
_comprobantes = [
    r[0]
    for r in _db.execute(
        _text(
            "SELECT id_comprobante FROM comprobantes_internos WHERE concepto IN ("
            + ",".join(f"'{c}'" for c in _CONCEPTOS_MOTOR)
            + ")"
        )
    ).all()
]
for _cid in _comprobantes:
    # El detalle va primero: `asiento_detalle` apunta al asiento, y si se borra
    # el asiento sin el detalle, el comprobante queda usado y la numeración
    # RC-000001 se corre para siempre.
    _db.execute(
        _text("DELETE FROM asiento_detalle WHERE id_asiento IN "
              "(SELECT id_asiento FROM asientos WHERE id_comprobante = :c)"),
        {"c": _cid},
    )
    _db.execute(
        _text("DELETE FROM asiento_origen WHERE id_asiento IN "
              "(SELECT id_asiento FROM asientos WHERE id_comprobante = :c)"),
        {"c": _cid},
    )
    _db.execute(
        _text("DELETE FROM asientos WHERE id_comprobante = :c"), {"c": _cid}
    )
    _db.execute(
        _text("DELETE FROM comprobantes_internos WHERE id_comprobante = :c"),
        {"c": _cid},
    )
_db.commit()
_db.close()
print("  (se limpiaron los asientos y comprobantes de corridas anteriores)")

# Cuentas del plan que vamos a usar
st, plan = req("GET", "/api/plan-cuentas", token=token)
por_codigo = {c["codigo"]: c for c in plan}


def cuenta(codigo):
    return por_codigo[codigo]["id_cuenta"]


CAJA = cuenta("1.1.01.01")            # deudora
CLIENTES = cuenta("1.1.03.01")        # deudora, auxiliar CLIENTE
PROVEEDORES = cuenta("2.1.01.01")     # acreedora, auxiliar PROVEEDOR
INGRESOS = cuenta("4.2.01")           # acreedora
GASTOS = cuenta("6.1.01")             # deudora
GRUPO = cuenta("1.1.01")              # agrupador: NO admite movimientos

print("\n== Comprobantes internos ==")

# Las fechas van dentro del ejercicio del estudio (01/09/2026 → 31/08/2027). El
# 01/09/2026 es el mismo día del ejercicio a propósito, para probar que el
# límite entra. Ver test_ejercicio.py para el caso de una fecha que cae fuera.
D1, D2, D3, D4 = "2026-09-01", "2026-09-02", "2026-09-03", "2027-01-05"

# --- el correlativo arranca en 1 y sube ---
st, c1 = req("POST", "/api/comprobantes-internos",
             {"codigo_comprobante": "OP", "fecha": D1, "concepto": "Pago proveedor"}, token)
check("crea el comprobante", st == 201, f"{st} {str(c1)[:120]}")
creados["comprobantes"].append(c1["id_comprobante"])
check("el número arranca en 1", c1["numero"] == 1, str(c1["numero"]))
check("se ve OP-000001", c1["numero_completo"] == "OP-000001", c1["numero_completo"])
check("el código y el número van separados",
      c1["codigo_comprobante"] == "OP" and isinstance(c1["numero"], int),
      f"{c1['codigo_comprobante']} / {c1['numero']}")
check("el año sale de la fecha", c1["anio"] == 2026, str(c1["anio"]))
check("y queda colgado del ejercicio", c1.get("id_ejercicio") is not None,
      str(c1.get("id_ejercicio")))

st, c2 = req("POST", "/api/comprobantes-internos",
             {"codigo_comprobante": "OP", "fecha": D2, "concepto": "Otro pago"}, token)
check("el correlativo sigue", c2["numero"] == 2, str(c2["numero"]))
check("se ve OP-000002", c2["numero_completo"] == "OP-000002", c2["numero_completo"])
creados["comprobantes"].append(c2["id_comprobante"])

# --- otro código tiene su propia numeración ---
st, c3 = req("POST", "/api/comprobantes-internos",
             {"codigo_comprobante": "RC", "fecha": D3, "concepto": "Cobranza"}, token)
check("cada código numera aparte (RC-000001)", c3["numero_completo"] == "RC-000001",
      c3["numero_completo"])
creados["comprobantes"].append(c3["id_comprobante"])

# --- el número NO se reinicia el 1 de enero (mismo ejercicio) ---
st, c4 = req("POST", "/api/comprobantes-internos",
             {"codigo_comprobante": "OP", "fecha": D4, "concepto": "Pago de enero"}, token)
check("cambia el año", c4["anio"] == 2027, str(c4["anio"]))
# Clave: enero 2027 sigue en el ejercicio 2026/2027, así que el número sigue
# en 3. Antes (cuando numeraba por año calendario) volvía a 1 y la
# numeración quedaba partida al medio del ejercicio.
check("pero el número NO vuelve a 1 (mismo ejercicio)", c4["numero"] == 3,
      str(c4["numero"]))
check("se ve OP-000003", c4["numero_completo"] == "OP-000003",
      c4["numero_completo"])
check("y es el mismo ejercicio que septiembre",
      c4["id_ejercicio"] == c1["id_ejercicio"],
      f"{c4['id_ejercicio']} vs {c1['id_ejercicio']}")
creados["comprobantes"].append(c4["id_comprobante"])

# --- validaciones ---
st, r = req("POST", "/api/comprobantes-internos",
            {"codigo_comprobante": "ZZ", "fecha": D1, "concepto": "x"}, token)
check("rechaza un código que no existe", st == 400, f"{st} {str(r)[:100]}")
st, r = req("POST", "/api/comprobantes-internos",
            {"codigo_comprobante": "OP", "fecha": D1, "concepto": "  "}, token)
# 400 (no el 422 de pydantic) porque "  " pasa el min_length pero al sacarle los
# espacios queda vacío, y eso lo avisa el service con un mensaje claro.
check("rechaza el concepto vacío", st == 400, str(st))

# --- los códigos internos ---
# Son 11: los 7 de fábrica (AI, AB, OP, RC, CO, TR, AJ), los tres de
# facturación (FV factura de venta, NC nota de crédito, ND nota de débito) y FP
# (factura de proveedor). NC y ND se agregaron el 02/10/2026 porque la nota de
# crédito tomaba un número de FV; FP se agregó el 02/10/2026 con las compras.
#
# FP es un código PROPIO y no comparte serie con FV a propósito: las dos son
# "factura" (una de venta y otra de proveedor) y si compartieran numeración el
# contador no podría distinguir un comprobante del otro. La numeración va por
# (código, ejercicio), así que FP-000001 y FV-000001 son series separadas.
st, cods = req("GET", "/api/comprobantes-internos/codigos", token=token)
check("los 11 códigos internos",
      {c["codigo"] for c in cods} == {"AI", "AB", "OP", "RC", "CO", "TR", "AJ",
                                     "FV", "NC", "ND", "FP"},
      str([c["codigo"] for c in cods]))
check("NC y ND son de FACTURA (las notas tienen su propia numeración)",
      any(c["codigo"] == "NC" and c["origen"] == "FACTURA" for c in cods)
      and any(c["codigo"] == "ND" and c["origen"] == "FACTURA" for c in cods),
      str(cods))
check("FV es el de la factura", any(c["codigo"] == "FV" and c["origen"] == "FACTURA" for c in cods),
      str(cods))
check("FP es el de la COMPRA, no el de la venta",
      any(c["codigo"] == "FP" and c["origen"] == "COMPRA" for c in cods),
      str(cods))
check("RC es el del recibo", any(c["codigo"] == "RC" and c["origen"] == "RECIBO" for c in cods),
      str(cods))
check("AB es el manual", any(c["codigo"] == "AB" and c["origen"] == "MANUAL" for c in cods),
      str(cods))

# --- listado y filtro ---
st, lst = req("GET", "/api/comprobantes-internos?codigo=OP", token=token)
check("filtra por código", st == 200 and all(c["codigo_comprobante"] == "OP" for c in lst),
      f"{st} {len(lst or [])}")
st, lst = req("GET", "/api/comprobantes-internos?anio=2027", token=token)
check("filtra por año", st == 200 and len(lst) == 1 and lst[0]["anio"] == 2027, str(len(lst or [])))

print("\n== Asientos y partida doble ==")

# --- crear un asiento ---
st, a = req("POST", "/api/asientos",
            {"fecha": "2026-09-10", "concepto": "Compra de mercadería",
             "id_comprobante": c1["id_comprobante"]}, token)
check("crea el asiento", st == 201, f"{st} {str(a)[:120]}")
aid = a["id_asiento"]
creados["asientos"].append(aid)
check("arranca en BORRADOR", a["estado"] == "BORRADOR", a["estado"])
check("totales en cero", str(a["total_debe"]) == "0.0000", str(a["total_debe"]))
check("hereda el comprobante", a["numero_completo"] == "OP-000001", str(a["numero_completo"]))

# --- guardar detalle desbalanceado ---
st, r = req("PUT", f"/api/asientos/{aid}/detalle", {"detalle": [
    {"id_cuenta": PROVEEDORES, "debe": 1000, "haber": 0},
    {"id_cuenta": GASTOS, "debe": 0, "haber": 900},
]}, token)
check("guarda las líneas", st == 200, f"{st} {str(r)[:150]}")
check("total debe = 1000", str(r["total_debe"]) == "1000.0000", str(r["total_debe"]))
check("total haber = 900", str(r["total_haber"]) == "900.0000", str(r["total_haber"]))
check("la diferencia es 100", str(r["diferencia"]) == "100.0000", str(r["diferencia"]))
check("no está balanceado", r["balanceado"] is False, str(r["balanceado"]))

# --- NO se puede contabilizar desbalanceado ---
st, r = req("POST", f"/api/asientos/{aid}/contabilizar", token=token)
check("NO contabiliza si no cierra", st == 400, f"{st} {str(r)[:150]}")
check("el error dice cuánto falta", "100" in str(r), str(r)[:150])
st, chk = req("GET", f"/api/asientos/{aid}", token=token)
check("sigue en BORRADOR", chk["estado"] == "BORRADOR", chk["estado"])

# --- el control general lo detecta ---
st, cg = req("GET", "/api/control-general", token=token)
check("el control general anda", st == 200 and "ok" in cg, f"{st} {str(cg)[:100]}")

# --- completar el detalle y contabilizar ---
st, r = req("PUT", f"/api/asientos/{aid}/detalle", {"detalle": [
    {"id_cuenta": PROVEEDORES, "debe": 0, "haber": 1000},
    {"id_cuenta": GASTOS, "debe": 1000, "haber": 0},
]}, token)
check("el detalle cierra", r["balanceado"] is True, str(r["diferencia"]))
check("diferencia = 0", str(r["diferencia"]) == "0.0000", str(r["diferencia"]))

st, r = req("POST", f"/api/asientos/{aid}/contabilizar", token=token)
check("ahora sí contabiliza", st == 200 and r["estado"] == "CONTABILIZADO",
      f"{st} {str(r)[:120]}")
check("el comprobante también queda contabilizado",
      True, "")

st, comp = req("GET", "/api/comprobantes-internos?codigo=OP", token=token)
op1 = next(c for c in comp if c["id_comprobante"] == c1["id_comprobante"])
check("el comprobante pasó a CONTABILIZADO", op1["estado"] == "CONTABILIZADO",
      op1["estado"])

# --- no se puede editar un contabilizado ---
st, r = req("PUT", f"/api/asientos/{aid}/detalle", {"detalle": [
    {"id_cuenta": GASTOS, "debe": 5, "haber": 0},
]}, token)
check("no deja editar un contabilizado", st == 409, f"{st} {str(r)[:120]}")
st, r = req("POST", f"/api/asientos/{aid}/contabilizar", token=token)
check("no deja contabilizar dos veces", st == 409, f"{st} {str(r)[:120]}")

print("\n== Reglas del detalle ==")

st, a2 = req("POST", "/api/asientos",
             {"fecha": "2026-09-05", "concepto": "Prueba reglas"}, token)
aid2 = a2["id_asiento"]
creados["asientos"].append(aid2)

st, r = req("PUT", f"/api/asientos/{aid2}/detalle", {"detalle": [
    {"id_cuenta": GRUPO, "debe": 100, "haber": 0},
]}, token)
check("no deja asentar a un agrupador", st == 400, f"{st} {str(r)[:150]}")
check("el error lo explica", "agrupador" in str(r).lower(), str(r)[:150])

st, r = req("PUT", f"/api/asientos/{aid2}/detalle", {"detalle": [
    {"id_cuenta": CAJA, "debe": -50, "haber": 0},
]}, token)
check("no deja importes negativos", st == 400, f"{st} {str(r)[:120]}")

st, r = req("PUT", f"/api/asientos/{aid2}/detalle", {"detalle": [
    {"id_cuenta": CAJA, "debe": 0, "haber": 0},
]}, token)
check("ignora la línea en cero", st == 200 and r["lineas"] == 0, f"{st} {str(r)[:120]}")

st, r = req("PUT", f"/api/asientos/{aid2}/detalle", {"detalle": [
    {"id_cuenta": 99999, "debe": 10, "haber": 0},
]}, token)
check("rechaza una cuenta inexistente", st == 400, f"{st} {str(r)[:120]}")

st, r = req("PUT", f"/api/asientos/{aid2}/detalle", {"detalle": [
    {"id_cuenta": CAJA, "debe": 100, "haber": 0, "tipo_auxiliar": "PERRO"},
]}, token)
check("rechaza un auxiliar raro", st == 400, f"{st} {str(r)[:120]}")

# --- las columnas de auxiliar existen aunque no se usen ---
st, r = req("PUT", f"/api/asientos/{aid2}/detalle", {"detalle": [
    {"id_cuenta": CAJA, "debe": 100, "haber": 0, "tipo_auxiliar": "CLIENTE", "id_auxiliar": 1},
    {"id_cuenta": INGRESOS, "debe": 0, "haber": 100},
]}, token)
check("acepta la línea con auxiliar (columnas preparadas)", st == 200, f"{st} {str(r)[:120]}")
req("POST", f"/api/asientos/{aid2}/contabilizar", token=token)

print("\n== Saldos ==")

st, sal = req("GET", "/api/saldos?con_movimientos=true", token=token)
check("trae los saldos", st == 200, f"{st} {str(sal)[:120]}")
por_cod = {s["codigo"]: s for s in sal}

# Por defecto trae TODAS las imputables, aunque estén en cero
st, todas = req("GET", "/api/saldos", token=token)
check("por defecto trae todas las imputables (141)", len(todas) == 141, str(len(todas)))
check("las que no se movieron están en cero",
      any(float(s["saldo"]) == 0 for s in todas), "ninguna en cero")

# Gastos es deudora: debe 1000 -> saldo +1000
check("gastos deudora: saldo = debe - haber = 1000",
      str(por_cod["6.1.01"]["saldo"]) == "1000.0000", str(por_cod["6.1.01"]["saldo"]))
# Proveedores es acreedora: haber 1000 -> saldo +1000 (a favor)
check("proveedores acreedora: saldo = haber - debe = 1000",
      str(por_cod["2.1.01.01"]["saldo"]) == "1000.0000", str(por_cod["2.1.01.01"]["saldo"]))
# Caja: debe 100
check("caja deudora con 100 en debe = 100",
      str(por_cod["1.1.01.01"]["saldo"]) == "100.0000", str(por_cod["1.1.01.01"]["saldo"]))
# Ingresos acreedora: haber 100 -> +100
check("ingresos acreedora con 100 en haber = 100",
      str(por_cod["4.2.01"]["saldo"]) == "100.0000", str(por_cod["4.2.01"]["saldo"]))
check("trae debe, haber y saldo",
      all(k in por_cod["6.1.01"] for k in ("total_debe", "total_haber", "saldo")), "")

# --- los saldos no incluyen borradores ---
st, sal_antes = req("GET", "/api/saldos", token=token)
total_antes = sum(float(s["saldo"]) for s in sal_antes)
st, a3 = req("POST", "/api/asientos",
             {"fecha": "2026-09-20", "concepto": "Borrador que no debe contar"}, token)
aid3 = a3["id_asiento"]
creados["asientos"].append(aid3)
req("PUT", f"/api/asientos/{aid3}/detalle", {"detalle": [
    {"id_cuenta": CAJA, "debe": 9999, "haber": 0},
    {"id_cuenta": INGRESOS, "debe": 0, "haber": 9999},
]}, token)
st, sal_despues = req("GET", "/api/saldos?con_movimientos=true", token=token)
check("un BORRADOR no cambia los saldos",
      sum(float(s["saldo"]) for s in sal_despues) == total_antes,
      f"{total_antes} -> {sum(float(s['saldo']) for s in sal_despues)}")

# --- anular sí los saca ---
req("POST", f"/api/asientos/{aid}/anular", token=token)
st, sal_anulado = req("GET", "/api/saldos", token=token)
por_cod2 = {s["codigo"]: s for s in sal_anulado}
check("al anular, la cuenta sigue en la lista",
      "6.1.01" in por_cod2, str(list(por_cod2)[:5]))
check("al anular, gastos queda en 0",
      str(por_cod2["6.1.01"]["saldo"]) == "0.0000", str(por_cod2["6.1.01"]["saldo"]))

# Un asiento ANULADO es terminal: no vuelve ni a borrador ni a contabilizado.
st, r = req("POST", f"/api/asientos/{aid}/contabilizar", token=token)
check("un asiento anulado no se puede volver a contabilizar", st == 409, f"{st} {str(r)[:100]}")
st, r = req("POST", f"/api/asientos/{aid}/borrador", token=token)
check("ni a borrador", st == 409, f"{st} {str(r)[:100]}")

print("\n== Control general ==")
st, cg = req("GET", "/api/control-general", token=token)
check("responde", st == 200, str(st))
check("el total debe cierra con el total haber",
      str(float(cg["total_debe"])) == str(float(cg["total_haber"])),
      f"{cg['total_debe']} vs {cg['total_haber']}")
check("no hay problemas", cg["ok"] is True and cg["problemas"] == [],
      str(cg["problemas"])[:200])

# Romper uno a propósito por SQL y ver que lo detecta
from sqlalchemy import text  # noqa: E402
import os, sys  # noqa: E402
sys.path.insert(0, _RUTA_BACKEND)
os.chdir(_RUTA_BACKEND)
from app.database import SessionLocal  # noqa: E402

db = SessionLocal()
db.execute(text(f"UPDATE asientos SET total_haber = total_haber + 50 WHERE id_asiento = {aid2}"))
db.commit()
db.close()

st, cg = req("GET", "/api/control-general", token=token)
check("detecta el asiento que no cierra", cg["ok"] is False, str(cg)[:150])
check("dice cuál es", len(cg["problemas"]) == 1 and cg["problemas"][0]["id_asiento"] == aid2,
      str(cg["problemas"])[:200])
check("dice por cuánto", cg["problemas"][0]["diferencia"] == "-50.0000",
      cg["problemas"][0]["diferencia"])

# Arreglarlo
db = SessionLocal()
db.execute(text(f"UPDATE asientos SET total_haber = total_haber - 50 WHERE id_asiento = {aid2}"))
db.commit()
db.close()
st, cg = req("GET", "/api/control-general", token=token)
check("arreglado, vuelve a estar ok", cg["ok"] is True, str(cg)[:150])

# ------------------------------------------------------------------ limpieza
print("\n== Limpieza ==")
db = SessionLocal()
# Los asientos cuelgan con ON DELETE CASCADE del detalle, así que alcanza con
# borrar el asiento. Los comprobantes quedan: se borran a mano.
for i in creados["asientos"]:
    db.execute(text(f"DELETE FROM asientos WHERE id_asiento = {i}"))
for i in creados["comprobantes"]:
    db.execute(text(f"DELETE FROM comprobantes_internos WHERE id_comprobante = {i}"))
db.commit()
db.close()

st, cg = req("GET", "/api/control-general", token=token)
check("todo limpio", cg["asientos_contabilizados"] == 0, str(cg["asientos_contabilizados"]))
st, sal = req("GET", "/api/saldos?con_movimientos=true", token=token)
check("no quedan saldos con movimiento", len(sal) == 0, str(len(sal)))
st, sal = req("GET", "/api/saldos", token=token)
check("pero las 141 cuentas siguen estando, en cero", len(sal) == 141, str(len(sal)))

print(f"\n{ok} OK / {len(fallos)} fallos")
if fallos:
    raise SystemExit(1)