"""El informe por centro de costos se arma con el PLAN DE CUENTAS, no con las
compras ni con los tipos de gasto.

Lo que se verifica acá:

  - los centros son las cuentas de segundo nivel de la rama 6 (GASTOS);
  - cada centro muestra SUS cuentas imputables;
  - los importes salen de los asientos **contabilizados**;
  - cada centro tiene su total, y el total general es la suma de los centros;
  - un asiento en borrador o anulado NO cuenta (no llegó al libro);
  - el filtro de fechas acota.

Para tener números reales la suite crea asientos manuales propios (una luz de
150.000 en 6.1.03 y publicidad de 30.000 en 6.2.01), mide la diferencia con lo
que había antes y después, y al final los borra por SQL. Por eso mide
*diferencias* y no valores absolutos: la base puede tener gastos reales cargados
y esta prueba no puede depender de eso.
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

CONCEPTO = "PRUEBA INFORME CENTROS"


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


def centro_por_codigo(datos, codigo_centro):
    for c in datos["centros"]:
        if c["codigo"] == codigo_centro:
            return c
    return None


def cuenta_por_codigo(centro, codigo):
    for k in centro["cuentas"]:
        if k["codigo"] == codigo:
            return k
    return None


def informe(token, desde=None, hasta=None):
    q = []
    if desde:
        q.append(f"desde={desde}")
    if hasta:
        q.append(f"hasta={hasta}")
    ruta = "/api/informes/centros-costos" + ("?" + "&".join(q) if q else "")
    return pedir("GET", ruta, token)[1]


def armar_asiento(token, fecha, lineas, contabilizar=True):
    codigo, a = pedir(
        "POST", "/api/asientos", token,
        {"fecha": fecha, "concepto": CONCEPTO, "codigo_comprobante": "AB"},
    )
    if codigo != 201:
        return None
    codigo, _ = pedir(
        "PUT", f"/api/asientos/{a['id_asiento']}/detalle", token, {"detalle": lineas}
    )
    if codigo != 200:
        return None
    if contabilizar:
        pedir("POST", f"/api/asientos/{a['id_asiento']}/contabilizar", token)
    return a["id_asiento"]


def borrar_asientos(token, ids):
    """Los asientos con comprobante propio no se pueden borrar por la API, así
    que se limpian por SQL. Un asiento ANULADO tampoco es borrable por API."""
    if not ids:
        return
    sys.path.insert(0, r"C:\proyecto-gestion-contable\backend")
    from sqlalchemy import text

    from app.database import SessionLocal

    db = SessionLocal()
    marcas = ",".join(str(i) for i in ids)
    # El comprobante se borra DESPUÉS del asiento: `asientos.id_comprobante` es
    # ON DELETE RESTRICT, así que al revés MySQL se niega.
    comps = [
        f[0] for f in db.execute(
            text("SELECT id_comprobante FROM asientos WHERE id_asiento IN ("
                 + marcas + ")")
        ).all()
    ]
    db.execute(
        text("DELETE FROM asiento_origen WHERE id_asiento IN (" + marcas + ")")
    )
    db.execute(text("DELETE FROM asiento_detalle WHERE id_asiento IN (" + marcas + ")"))
    db.execute(text("DELETE FROM asientos WHERE id_asiento IN (" + marcas + ")"))
    if comps:
        db.execute(
            text("DELETE FROM comprobantes_internos WHERE id_comprobante IN ("
                 + ",".join(str(c) for c in comps) + ")")
        )
    db.commit()
    db.close()


# ---------------------------------------------------------------------
token = pedir("POST", "/api/auth/login",
              cuerpo={"usuario": "admin", "password": "admin123"})[1]["access_token"]

# --- la rama de GASTOS del plan --------------------------------------
codigo, arbol = pedir("GET", "/api/informes/centros-cuentas", token)
chequear("El endpoint de centros responde 200", codigo == 200, str(codigo))
chequear("La raíz es la cuenta 6 (GASTOS)", arbol["codigo"] == "6", str(arbol))

codigos = [c["codigo"] for c in arbol["centros"]]
chequear(
    "Los centros son 6.1, 6.2, 6.3 y 6.4",
    codigos == ["6.1", "6.2", "6.3", "6.4"],
    str(codigos),
)
chequear(
    "Administración tiene sus 10 cuentas de gasto",
    len(arbol["centros"][0]["cuentas"]) == 10,
    str(len(arbol["centros"][0]["cuentas"])),
)
chequear(
    "Comercialización tiene publicidad y combustible",
    [k["codigo"] for k in arbol["centros"][1]["cuentas"]] == ["6.2.01", "6.2.02"],
)

# --- el informe ------------------------------------------------------
codigo, datos = pedir("GET", "/api/informes/centros-costos", token)
chequear("El informe responde 200", codigo == 200, str(codigo))
chequear("El informe trae los 4 centros", len(datos["centros"]) == 4,
         str(len(datos["centros"])))
chequear("Cada centro trae su total", all("total" in c for c in datos["centros"]))
chequear("Cada centro trae sus cuentas",
         all(len(c["cuentas"]) > 0 for c in datos["centros"]))

# Lo que hay HOY, antes de que esta suite toque nada: es la línea de base.
antes = {
    c["codigo"]: c["total"]
    for c in informe(token)["centros"]
}

# Para el filtro de fechas, una línea de base CON EL MISMO filtro: comparar un
# informe sin fechas contra uno de 2027 no dice nada si la base tiene
# movimientos de 2026. (Sin esto el test pasaba de casualidad porque las
# cuentas de gasto estaban en cero; el día que se carguen de verdad falla.)
FUERA = {"desde": "2027-01-01", "hasta": "2027-12-31"}
antes_fuera = {
    c["codigo"]: c["total"]
    for c in informe(token, **FUERA)["centros"]
}

LUZ = buscar_cuenta(token, "6.1.03")
PUB = buscar_cuenta(token, "6.2.01")
PAGAR = buscar_cuenta(token, "2.1.01.02")
chequear("Las cuentas del plan existen", all([LUZ, PUB, PAGAR]), f"{LUZ} {PUB} {PAGAR}")

nuevos = []
try:
    # 150.000 de luz (administración) y 30.000 de publicidad (comercialización).
    # El Haber tiene que ser IGUAL al Debe: si no, el asiento no cierra,
    # contabilizar lo rechaza y queda en borrador — que es justo lo que el
    # informe tiene que NO contar.
    nuevos.append(
        armar_asiento(token, "2026-09-15", [
            {"id_cuenta": LUZ, "debe": "150000.00", "haber": "0.00"},
            {"id_cuenta": PAGAR, "debe": "0.00", "haber": "150000.00"},
        ])
    )
    nuevos.append(
        armar_asiento(token, "2026-09-15", [
            {"id_cuenta": PUB, "debe": "30000.00", "haber": "0.00"},
            {"id_cuenta": PAGAR, "debe": "0.00", "haber": "30000.00"},
        ])
    )

    d = informe(token)
    admin = centro_por_codigo(d, "6.1")
    comer = centro_por_codigo(d, "6.2")

    chequear(
        "La luz de agua aparece en Administración",
        cuenta_por_codigo(admin, "6.1.03")["total"] - antes["6.1"] == 150000.0,
        str(cuenta_por_codigo(admin, "6.1.03")),
    )
    chequear(
        "La publicidad aparece en Comercialización",
        cuenta_por_codigo(comer, "6.2.01")["total"] - antes["6.2"] == 30000.0,
        str(cuenta_por_codigo(comer, "6.2.01")),
    )
    chequear(
        "El total de Administración subió 150.000",
        admin["total"] - antes["6.1"] == 150000.0,
        f"{admin['total']} vs {antes['6.1']}",
    )
    chequear(
        "El total de Comercialización subió 30.000",
        comer["total"] - antes["6.2"] == 30000.0,
        f"{comer['total']} vs {antes['6.2']}",
    )
    chequear(
        "El total del centro es la suma de sus cuentas",
        round(sum(k["total"] for k in admin["cuentas"]), 2)
        == round(admin["total"], 2),
        f"{admin['total']} vs {sum(k['total'] for k in admin['cuentas'])}",
    )
    chequear(
        "El total general es la suma de los centros",
        round(sum(c["total"] for c in d["centros"]), 2)
        == round(d["total_general"], 2),
        str(d["total_general"]),
    )
    chequear(
        "Financiero y Otros NO se movieron",
        centro_por_codigo(d, "6.3")["total"] == antes["6.3"]
        and centro_por_codigo(d, "6.4")["total"] == antes["6.4"],
    )

    # --- el filtro de fechas -----------------------------------------
    fuera = informe(token, **FUERA)
    chequear(
        "Fuera del período no cuenta (contra su propia línea de base)",
        all(c["total"] == antes_fuera[c["codigo"]] for c in fuera["centros"]),
        str({c["codigo"]: (c["total"], antes_fuera[c["codigo"]])
             for c in fuera["centros"]}),
    )

    # --- un asiento en BORRADOR no cuenta ----------------------------
    sin_contabilizar = armar_asiento(
        token, "2026-09-15",
        [
            {"id_cuenta": LUZ, "debe": "999.00", "haber": "0.00"},
            {"id_cuenta": PAGAR, "debe": "0.00", "haber": "999.00"},
        ],
        contabilizar=False,
    )
    nuevos.append(sin_contabilizar)
    d2 = informe(token)
    chequear(
        "Un asiento en borrador NO cuenta",
        round(centro_por_codigo(d2, "6.1")["total"], 2)
        == round(antes["6.1"] + 150000.0, 2),
        str(centro_por_codigo(d2, "6.1")["total"]),
    )

    # --- un asiento ANULADO tampoco cuenta ----------------------------
    pedir("POST", f"/api/asientos/{nuevos[0]}/anular", token)
    d3 = informe(token)
    chequear(
        "Un asiento anulado NO cuenta (vuelve a la línea de base)",
        round(centro_por_codigo(d3, "6.1")["total"], 2) == round(antes["6.1"], 2),
        f"{centro_por_codigo(d3, '6.1')['total']} vs {antes['6.1']}",
    )

    # --- el Excel sale -----------------------------------------------
    # El .xlsx es binario: no se puede leer como JSON, así que se pide crudo y
    # se mira que arranque con la firma de un archivo de Excel (PK = zip).
    req = urllib.request.Request(
        BASE + "/api/informes/centros-costos/export.xlsx?desde=2000-01-01"
               "&hasta=2100-01-01",
        method="GET",
    )
    req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=40) as r:
        crudo = r.read()
    chequear("El Excel se genera", r.status == 200, str(r.status))
    chequear(
        "El Excel viene completo (firma de Excel/zip)",
        len(crudo) > 3000 and crudo[:2] == b"PK",
        f"{len(crudo)} bytes, empieza {crudo[:2]!r}",
    )

finally:
    borrar_asientos(token, [i for i in nuevos if i])

# --- después de limpiar, el informe vuelve a como estaba -------------
d = informe(token)
chequear(
    "Al borrar los asientos de prueba el informe vuelve a la línea de base",
    all(
        round(c["total"], 2) == round(antes[c["codigo"]], 2)
        for c in d["centros"]
    ),
    str({c["codigo"]: c["total"] for c in d["centros"]}),
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
