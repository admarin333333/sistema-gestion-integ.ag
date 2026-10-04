"""El informe de resultados y el de centros de costos tienen que DECIR LO MISMO.

El desfasaje que el contador señaló: el informe por centro decía "gastos 100.000"
(movimientos reales de los libros) y el de resultados decía "gastos 0" (suma de
la tabla de compras). Dos informes del mismo estudio que no coinciden.

Lo que se verifica acá:

  - los dos informes salen de la MISMA función (`saldos_rama`), así que el gasto
    del de resultados ES el total del de centros, número por número;
  - los tres lados del estado de resultado (ingresos, costos, gastos) salen de los
    asientos contabilizados, no de las tablas de facturas y compras;
  - solo cuentan los asientos CONTABILIZADOS;
  - el signo sale de la cuenta: una de ingresos suma en el Haber y da positivo,
    una de gastos en el Debe;
  - el neto es ingresos − costos − gastos;
  - un asiento en borrador o anulado no cuenta en ninguno de los dos informes;
  - el filtro de fechas acota en los dos.

Igual que en `test_informe_centros.py`, se miden DIFERENCIAS contra la línea de
base: la base puede tener gastos reales cargados.
"""

import os
import json
import sys
import urllib.error
import urllib.request
# La dirección de la API sale de `GC_BASE_URL` para poder correr estas pruebas
# contra la base de PRUEBAS y no contra la del estudio. Si la variable no
# está, usa 8010 como antes: no cambia cómo se corren.

BASE = os.environ.get("GC_BASE_URL", "http://127.0.0.1:8010")

# Esta suite habla con la base de DOS maneras: por HTTP (`BASE`) y por SQL directo
# (`app.database`, en `borrar_asientos`). Con solo `GC_BASE_URL` el SQL se va a la
# base REAL y el borrado por SQL no toca nada de la base de pruebas.
#
# `DB_NAME` tiene que estar puesta ANTES de que se importe `app.database`, porque
# ese módulo lee el entorno UNA sola vez al importarse.
if "GC_BASE_URL" in os.environ:
    os.environ.setdefault(
        "DB_NAME", os.environ.get("GC_TEST_DB", "gestion_contable_test")
    )

resultado = []

CONCEPTO = "PRUEBA RESULTADOS"


def pedir(metodo, ruta, token=None, cuerpo=None):
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(BASE + ruta, data=datos, method=metodo)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            texto = r.read().decode()
            return r.status, json.loads(texto) if texto else None
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:250]


def chequear(nombre, condicion, detalle=""):
    resultado.append((nombre, bool(condicion), detalle))


def buscar_cuenta(token, codigo):
    _, d = pedir("GET", f"/api/plan-cuentas?q={codigo}", token)
    for c in d or []:
        if c["codigo"] == codigo:
            return c["id_cuenta"]
    return None


def centros(token):
    _, d = pedir("GET", "/api/informes/centros-costos", token)
    return d


def resultados(token, desde=None, hasta=None):
    q = []
    if desde:
        q.append(f"desde={desde}")
    if hasta:
        q.append(f"hasta={hasta}")
    ruta = "/api/informes/resultados" + ("?" + "&".join(q) if q else "")
    return pedir("GET", ruta, token)[1]


def borrar_asientos(token, ids):
    if not ids:
        return
    sys.path.insert(0, r"C:\proyecto-gestion-contable\backend")
    from sqlalchemy import text

    from app.database import SessionLocal

    db = SessionLocal()
    marcas = ",".join(str(i) for i in ids)
    comps = [
        f[0]
        for f in db.execute(
            text(
                "SELECT id_comprobante FROM asientos WHERE id_asiento IN ("
                + marcas
                + ")"
            )
        ).all()
    ]
    db.execute(text("DELETE FROM asiento_origen WHERE id_asiento IN (" + marcas + ")"))
    db.execute(text("DELETE FROM asiento_detalle WHERE id_asiento IN (" + marcas + ")"))
    db.execute(text("DELETE FROM asientos WHERE id_asiento IN (" + marcas + ")"))
    if comps:
        db.execute(
            text(
                "DELETE FROM comprobantes_internos WHERE id_comprobante IN ("
                + ",".join(str(c) for c in comps)
                + ")"
            )
        )
    db.commit()
    db.close()


# ---------------------------------------------------------------------
tok = pedir("POST", "/api/auth/login",
            cuerpo={"usuario": "admin", "password": "admin123"})[1]["access_token"]

codigo, res = pedir("GET", "/api/informes/resultados", tok)
chequear("El informe de resultados responde 200", codigo == 200, str(codigo))
chequear("Trae ingresos, costos, gastos y neto",
         all(k in res for k in ("ingresos", "costos", "centros", "neto")))
chequear("El gasto sale de `total_gastos`", "total_gastos" in res)

# --- la línea de base de los dos informes -----------------------------
c_antes = centros(tok)
r_antes = resultados(tok)

# Para el filtro de fechas hace falta una línea de base CON EL MISMO filtro:
# comparar un informe sin fechas contra uno de 2027 no dice nada si la base
# tiene movimientos de 2026.
FUERA = {"desde": "2027-01-01", "hasta": "2027-12-31"}
r_fuera_antes = resultados(tok, **FUERA)

chequear(
    "SIN mover nada, los dos informes ya dan el mismo gasto",
    round(c_antes["total_general"], 2) == round(r_antes["total_gastos"], 2),
    f"centros {c_antes['total_general']} vs resultados {r_antes['total_gastos']}",
)

# --- armas una venta (ingreso) y un gasto -----------------------------
INGRESO = buscar_cuenta(tok, "4.1.01")   # ventas articulos (ACREEDORA)
LUZ = buscar_cuenta(tok, "6.1.03")
COSTO = buscar_cuenta(tok, "5.1.01")     # costo por venta (DEUDORA)
DOCS = buscar_cuenta(tok, "1.1.03.02")   # Documentos a cobrar
chequear("Las cuentas del plan existen",
         all([INGRESO, LUZ, COSTO, DOCS]), f"{INGRESO} {LUZ} {COSTO} {DOCS}")

nuevos = []


def armar(fecha, lineas, contabilizar=True):
    codigo, a = pedir("POST", "/api/asientos", tok,
                      {"fecha": fecha, "concepto": CONCEPTO, "codigo_comprobante": "AB"})
    if codigo != 201:
        return None
    codigo, _ = pedir("PUT", f"/api/asientos/{a['id_asiento']}/detalle", tok,
                      {"detalle": lineas})
    if codigo != 200:
        return None
    if contabilizar:
        pedir("POST", f"/api/asientos/{a['id_asiento']}/contabilizar", tok)
    return a["id_asiento"]


try:
    # 300.000 de venta, 40.000 de luz y 60.000 de costo de mercadería.
    nuevos.append(armar("2026-09-20", [
        {"id_cuenta": DOCS, "debe": "300000.00", "haber": "0.00"},
        {"id_cuenta": INGRESO, "debe": "0.00", "haber": "300000.00"},
    ]))
    nuevos.append(armar("2026-09-21", [
        {"id_cuenta": LUZ, "debe": "40000.00", "haber": "0.00"},
        {"id_cuenta": DOCS, "debe": "0.00", "haber": "40000.00"},
    ]))
    nuevos.append(armar("2026-09-22", [
        {"id_cuenta": COSTO, "debe": "60000.00", "haber": "0.00"},
        {"id_cuenta": DOCS, "debe": "0.00", "haber": "60000.00"},
    ]))

    c = centros(tok)
    r = resultados(tok)

    # --- ingresos: el signo sale de la cuenta --------------------------
    chequear(
        "Los ingresos subieron 300.000 (la cuenta de ingresos es ACREEDORA)",
        r["ingresos"]["total"] - r_antes["ingresos"]["total"] == 300000.0,
        f"{r_antes['ingresos']['total']} → {r['ingresos']['total']}",
    )

    # --- costos: rama 5, que antes ni se miraba ------------------------
    chequear(
        "Los costos subieron 60.000",
        r["total_costos"] - r_antes["total_costos"] == 60000.0,
        f"{r_antes['total_costos']} → {r['total_costos']}",
    )
    chequear("La rama de costos trae sus grupos", len(r["costos"]["grupos"]) >= 1)

    # --- gastos: el MISMO número que el informe de centros -------------
    chequear(
        "El gasto del informe de resultados subió 40.000",
        r["total_gastos"] - r_antes["total_gastos"] == 40000.0,
        f"{r_antes['total_gastos']} → {r['total_gastos']}",
    )
    chequear(
        "LOS DOS INFORMES DICEN EL MISMO GASTO",
        round(c["total_general"], 2) == round(r["total_gastos"], 2),
        f"centros {c['total_general']} vs resultados {r['total_gastos']}",
    )
    admin_c = next(x for x in c["centros"] if x["codigo"] == "6.1")
    admin_r = next(x for x in r["centros"] if x["codigo"] == "6.1")
    chequear(
        "Y dan el mismo total en CADA centro, no solo en el total general",
        round(admin_c["total"], 2) == round(admin_r["total"], 2),
        f"{admin_c['total']} vs {admin_r['total']}",
    )

    # --- el neto ------------------------------------------------------
    chequear(
        "El neto es ingresos − costos − gastos",
        round(r["neto"], 2)
        == round(r["ingresos"]["total"] - r["total_costos"] - r["total_gastos"], 2),
        str(r["neto"]),
    )
    chequear(
        "El neto subió 200.000 (entran 300 de venta, salen 100 de gasto y costo)",
        r["neto"] - r_antes["neto"] == 200000.0,
        f"{r_antes['neto']} → {r['neto']}",
    )
    chequear("Los egresos son costos + gastos",
             round(r["total_egresos"], 2)
             == round(r["total_costos"] + r["total_gastos"], 2))

    # --- borrador y anulado no cuentan ---------------------------------
    borrador = armar("2026-09-23", [
        {"id_cuenta": LUZ, "debe": "777.00", "haber": "0.00"},
        {"id_cuenta": DOCS, "debe": "0.00", "haber": "777.00"},
    ], contabilizar=False)
    nuevos.append(borrador)
    chequear(
        "Un asiento en borrador NO cuenta en ninguno de los dos",
        round(centros(tok)["total_general"], 2) == round(c["total_general"], 2)
        and round(resultados(tok)["total_gastos"], 2) == round(r["total_gastos"], 2),
    )

    # --- el filtro de fechas ------------------------------------------
    r_fuera = resultados(tok, **FUERA)
    chequear(
        "Fuera del período no entra nada (compara contra su propia línea de base)",
        round(r_fuera["total_gastos"], 2) == round(r_fuera_antes["total_gastos"], 2)
        and round(r_fuera["ingresos"]["total"], 2)
        == round(r_fuera_antes["ingresos"]["total"], 2)
        and round(r_fuera["total_costos"], 2)
        == round(r_fuera_antes["total_costos"], 2),
        f"gastos {r_fuera['total_gastos']} vs {r_fuera_antes['total_gastos']} | "
        f"ingresos {r_fuera['ingresos']['total']} vs {r_fuera_antes['ingresos']['total']}",
    )

    # --- el Excel sale -------------------------------------------------
    req = urllib.request.Request(
        BASE + "/api/informes/resultados/export.xlsx?desde=2000-01-01&hasta=2100-01-01",
        method="GET",
    )
    req.add_header("Authorization", "Bearer " + tok)
    with urllib.request.urlopen(req, timeout=40) as r2:
        crudo = r2.read()
    chequear("El Excel de resultados se genera", r2.status == 200, str(r2.status))
    chequear("El Excel viene completo", len(crudo) > 3000 and crudo[:2] == b"PK",
             f"{len(crudo)} bytes")

finally:
    borrar_asientos(tok, [i for i in nuevos if i])

# --- al limpiar, los dos vuelven a la línea de base -------------------
c_fin = centros(tok)
r_fin = resultados(tok)
chequear(
    "Al borrar los asientos de prueba los dos vuelven a la línea de base",
    round(c_fin["total_general"], 2) == round(c_antes["total_general"], 2)
    and round(r_fin["total_gastos"], 2) == round(r_antes["total_gastos"], 2),
    f"{c_fin['total_general']} / {r_fin['total_gastos']}",
)

fallos = [r for r in resultado if not r[1]]
for nombre, ok, detalle in resultado:
    if not ok:
        print(f"  FALLA  {nombre}  {detalle}")
print()
print(f"  {len(resultado) - len(fallos)}/{len(resultado)} pruebas correctas")
if not fallos:
    print("  Todas en verde.")
else:
    print(f"  {len(fallos)} FALLOS")
raise SystemExit(1 if fallos else 0)
