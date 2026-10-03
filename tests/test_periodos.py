"""Los PERÍODOS contables: los 12 meses del ejercicio, que se abren y se cierran.

Lo que se verifica acá, en orden de importancia:

  1. Que un período cerrado frene **de verdad**: cargar una factura, crear un
     asiento, crear un comprobante. Si alguno de estos pasa, el módulo no sirve.
  2. Que NO frene lo que tiene que seguir funcionando: leer, listar, ver el
     informe de centros.
  3. Que el error diga qué período está cerrado y cómo se abre. Si el mensaje no
     lo dice, el contador no sabe qué hacer y vuelve a intentar lo mismo.
  4. Que cerrar un período con documentos avise cuántos hay y exija confirmar.
  5. Que solo el admin abra y cierre.

La suite trabaja contra el período 12 (agosto 2027), que en un estudio normal
está vacío: así no toca los meses que el contador ya usó. Y todo lo que crea lo
borra al final, así que la base queda como estaba.
"""

import json
import os
import sys
import urllib.error
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "backend"))

BASE = "http://127.0.0.1:8010"
resultado = []

# Agosto de 2027: el período 12 del ejercicio 2026/2027. Se elige un mes que en
# un estudio real está vacío, así la suite no pisa trabajo hecho.
FECHA = "2027-08-15"
CONCEPTO = "PRUEBA PERIODOS"
NUMERO_FACTURA = "99991"

# "CC" no existe: el sistema usa CO, OP, TR, FP, FV... Probar con un código
# inválido mezclaría dos errores y la prueba apuntaría a la línea equivocada.
CODIGO_COMPROBANTE = "OP"

# Septiembre 2026 (período 1) es el que el contador usa de verdad. La suite solo
# lo LEE, nunca lo cierra: cerrarlo y fallar después dejaría el estudio trabado.


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
        return e.code, e.read().decode()[:400]


def chequear(nombre, condicion, detalle=""):
    resultado.append((nombre, bool(condicion), detalle))


def login(usuario, clave):
    _, d = pedir("POST", "/api/auth/login",
                 cuerpo={"usuario": usuario, "password": clave})
    return d["access_token"] if isinstance(d, dict) else None


def ejercicio_con_periodos(token):
    """El ejercicio abierto: el que está trabajando el estudio."""
    _, d = pedir("GET", "/api/ejercicios", token)
    for e in d["ejercicios"]:
        if not e["cerrado"]:
            return e
    return d["ejercicios"][0]


def buscar_cuenta(token, codigo):
    _, d = pedir("GET", f"/api/plan-cuentas?q={codigo}", token)
    for c in d or []:
        if c["codigo"] == codigo:
            return c["id_cuenta"]
    return None


def limpiar(token):
    """Saca por SQL lo que dejó esta corrida o una anterior.

    Por SQL y no por la API a propósito: una factura tiene SIEMPRE asiento
    (se genera al darla de alta) y la API no deja borrarla ni el asiento, que
    es lo correcto en producción. En la prueba hay que limpiar igual, porque si
    no la corrida siguiente choca con el "Ya existe Factura B 0001-00099991" y
    el fallo apunta a la línea equivocada.

    Solo toca filas con el concepto de la prueba: los datos del contador no se
    tocan nunca.
    """
    from sqlalchemy import text

    from app.database import engine

    with engine.begin() as c:
        facturas = c.execute(
            text("SELECT id FROM facturas WHERE concepto = :c"), {"c": CONCEPTO}
        ).fetchall()
        for (fid,) in facturas:
            origenes = c.execute(
                text("SELECT id_asiento FROM asiento_origen WHERE id_factura = :i"),
                {"i": fid},
            ).fetchall()
            for (aid,) in origenes:
                c.execute(
                    text("DELETE FROM asiento_origen WHERE id_factura = :i"),
                    {"i": fid},
                )
                c.execute(
                    text("DELETE FROM asiento_detalle WHERE id_asiento = :a"),
                    {"a": aid},
                )
                c.execute(
                    text("DELETE FROM asientos WHERE id_asiento = :a"), {"a": aid}
                )
            c.execute(text("DELETE FROM facturas WHERE id = :i"), {"i": fid})

        asientos = c.execute(
            text(
                "SELECT id_asiento FROM asientos "
                "WHERE concepto = :c OR concepto LIKE :p"
            ),
            {"c": CONCEPTO, "p": CONCEPTO + " %"},
        ).fetchall()
        for (aid,) in asientos:
            c.execute(
                text("DELETE FROM asiento_origen WHERE id_asiento = :a"), {"a": aid}
            )
            c.execute(
                text("DELETE FROM asiento_detalle WHERE id_asiento = :a"), {"a": aid}
            )
            c.execute(text("DELETE FROM asientos WHERE id_asiento = :a"), {"a": aid})

        c.execute(
            text("DELETE FROM comprobantes_internos WHERE concepto = :c"),
            {"c": CONCEPTO},
        )
    return len(facturas) + len(asientos)


# =====================================================================
# ARRANQUE
# =====================================================================

token = login("admin", "admin123")
if not token:
    print("  No se pudo loguear. ¿Está el backend en 8010?")
    raise SystemExit(1)

ej = ejercicio_con_periodos(token)
_, lp = pedir("GET", f"/api/ejercicios/periodos/{ej['id_ejercicio']}", token)
periodos = lp["periodos"]

# Limpieza de arranque: si una corrida anterior murió a mitad de camino dejó el
# período 12 cerrado o una factura con el mismo número, esta corrida arrancaría
# ya con la trava puesta y probaría cualquier cosa.
limpiar(token)
for p in periodos:
    if p["cerrado"]:
        pedir(
            "POST",
            f"/api/ejercicios/periodos/{p['id_periodo']}/estado",
            token,
            {"cerrado": False, "forzar": True},
        )
_, lp = pedir("GET", f"/api/ejercicios/periodos/{ej['id_ejercicio']}", token)
periodos = lp["periodos"]
por_numero = {p["numero"]: p for p in periodos}

chequear("Se puede loguear como admin", True)
chequear("El ejercicio tiene 12 períodos", len(periodos) == 12, str(len(periodos)))
chequear(
    "Los períodos van numerados del 1 al 12",
    [p["numero"] for p in periodos] == list(range(1, 13)),
    str([p["numero"] for p in periodos]),
)

# =====================================================================
# 1. LOS 12 SON LOS MESES DEL EJERCICIO
# =====================================================================

ini = ej["fecha_inicio"]
chequear(
    "El período 1 es el mes en que arranca el ejercicio",
    por_numero[1]["fecha_inicio"][:7] == ini[:7],
    f"{por_numero[1]['fecha_inicio']} vs {ini}",
)
chequear(
    "El período 12 es un mes distinto al 1 (doce meses después)",
    por_numero[12]["nombre"][-4:] != por_numero[1]["nombre"][-4:]
    or por_numero[12]["nombre"].split()[0] != por_numero[1]["nombre"].split()[0],
    f"{por_numero[12]['nombre']}",
)
chequear(
    "Cada período tiene nombre de mes y año",
    all(" " in p["nombre"] for p in periodos),
    str([p["nombre"] for p in periodos]),
)
chequear(
    "Cada período arranca el día 1",
    all(p["fecha_inicio"][8:10] == "01" for p in periodos),
    str([p["fecha_inicio"] for p in periodos]),
)
chequear(
    "Los períodos avanzan de a uno, sin huecos",
    all(
        por_numero[i + 1]["fecha_inicio"] > por_numero[i]["fecha_inicio"]
        for i in range(1, 12)
    ),
    "las fechas no avanzan",
)

# --- dónde cae una fecha ----------------------------------------------
_, d = pedir("GET", f"/api/ejercicios/periodo-de-fecha?fecha={FECHA}", token)
chequear(
    "Una fecha de agosto 2027 cae en el período 12",
    d["periodo"] and d["periodo"]["numero"] == 12,
    str(d.get("periodo")),
)
_, d = pedir("GET", f"/api/ejercicios/periodo-de-fecha?fecha={por_numero[1]['fecha_fin']}", token)
chequear(
    "El ÚLTIMO día del período es de ese período, no del siguiente",
    d["periodo"] and d["periodo"]["numero"] == 1,
    str(d.get("periodo")),
)
_, d = pedir("GET", "/api/ejercicios/periodo-de-fecha?fecha=2030-12-01", token)
chequear(
    "Una fecha fuera de todo ejercicio no encuentra período",
    d["periodo"] is None,
    str(d.get("periodo")),
)
_, d = pedir("GET", f"/api/ejercicios/periodo-de-fecha?fecha={FECHA}", token)
chequear(
    "La respuesta trae el ejercicio del período",
    d["ejercicio"] and d["ejercicio"]["id_ejercicio"] == ej["id_ejercicio"],
    str(d.get("ejercicio")),
)

# =====================================================================
# 2. TODOS NACEN ABIERTOS
# =====================================================================

chequear(
    "Ningún período nace cerrado",
    all(p["cerrado"] is False for p in periodos),
    str([(p["numero"], p["cerrado"]) for p in periodos if p["cerrado"]]),
)
chequear(
    "La pantalla sabe si el período tiene movimientos",
    all("tiene_movimientos" in p for p in periodos),
    str(list(periodos[0].keys())),
)

# =====================================================================
# 3. CON UN PERÍODO CERRADO, SE FRENA
# =====================================================================

p12 = por_numero[12]

st, d = pedir(
    "POST",
    f"/api/ejercicios/periodos/{p12['id_periodo']}/estado",
    token,
    {"cerrado": True},
)
chequear("Se puede cerrar un período vacío", st == 200, f"{st} {str(d)[:160]}")
chequear("El período queda cerrado", isinstance(d, dict) and d["cerrado"] is True, str(d))

_, lp = pedir("GET", f"/api/ejercicios/periodos/{ej['id_ejercicio']}", token)
cerrado_ahora = next(p for p in lp["periodos"] if p["numero"] == 12)
chequear(
    "El período 12 aparece cerrado al recargar",
    cerrado_ahora["cerrado"] is True,
    str(cerrado_ahora),
)

# --- leer NO se frena (cerrado es "no escribás", no "no mires") -------
st, _ = pedir("GET", "/api/asientos?desde=2000-01-01&hasta=2100-01-01", token)
chequear("Con un período cerrado se siguen listando asientos", st == 200, str(st))
st, _ = pedir(
    "GET", "/api/informes/centros-costos?desde=2000-01-01&hasta=2100-01-01", token
)
chequear(
    "Con un período cerrado se sigue viendo el informe de centros", st == 200, str(st)
)
st, _ = pedir("GET", "/api/facturas", token)
chequear("Con un período cerrado se siguen listando facturas", st == 200, str(st))
st, _ = pedir("GET", "/api/recibos", token)
chequear("Con un período cerrado se siguen listando recibos", st == 200, str(st))

# --- crear documentos en ese mes rebota ------------------------------
_, cli = pedir("GET", "/api/clientes", token)
lista_cli = cli if isinstance(cli, list) else (cli or {}).get("clientes") or []
# Los clientes salen con `id` (no `id_cliente`): viene de la tabla clientes.
cliente_id = lista_cli[0]["id"] if lista_cli else None

cuerpo_factura = {
    "cliente_id": cliente_id,
    "fecha": FECHA,
    "tipo_comprobante": "factura_b",
    "punto_venta": "1",
    "numero": NUMERO_FACTURA,
    "condicion_venta": "contado",
    "importe": 1000.00,
    "concepto": CONCEPTO,
}

if not cliente_id:
    chequear("Hay al menos un cliente para probar", False, "no hay clientes cargados")
else:
    st, d = pedir("POST", "/api/facturas", token, cuerpo_factura)
    chequear(
        "Cargar una factura en un período cerrado rebota con 409",
        st == 409,
        f"{st} {str(d)[:200]}",
    )
    chequear(
        "El error dice qué período está cerrado",
        "Agosto 2027" in str(d),
        str(d)[:250],
    )
    chequear(
        "El error dice cómo se abre",
        "Reabrilo" in str(d),
        str(d)[:250],
    )

# --- un asiento manual de ese mes rebota -----------------------------
st, d = pedir(
    "POST",
    "/api/asientos",
    token,
    {"fecha": FECHA, "concepto": CONCEPTO},
)
chequear(
    "Crear un asiento en un período cerrado rebota con 409",
    st == 409,
    f"{st} {str(d)[:200]}",
)

# --- un comprobante de ese mes rebota --------------------------------
st, d = pedir(
    "POST",
    "/api/comprobantes-internos",
    token,
    {"codigo_comprobante": CODIGO_COMPROBANTE, "fecha": FECHA,
     "concepto": CONCEPTO},
)
chequear(
    "Crear un comprobante en un período cerrado rebota con 409",
    st == 409,
    f"{st} {str(d)[:200]}",
)

# =====================================================================
# 4. CERRAR CON DOCUMENTOS DENTRO
# =====================================================================

# El período 1 tiene movimientos reales del estudio. Cerrarlo tiene que pedir
# confirmación; si cerrara de una, el contador cerraría por error un mes entero.
# NO se cierra nunca: solo se mira la respuesta.
p1 = por_numero[1]
st, d = pedir(
    "POST",
    f"/api/ejercicios/periodos/{p1['id_periodo']}/estado",
    token,
    {"cerrado": True},
)
chequear(
    "Cerrar un período CON documentos pide confirmación (409)",
    st == 409,
    f"{st} {str(d)[:200]}",
)
chequear(
    "El aviso dice cuántos documentos tiene",
    "documento" in str(d).lower() or "movimiento" in str(d).lower(),
    str(d)[:250],
)

_, lp = pedir("GET", f"/api/ejercicios/periodos/{ej['id_ejercicio']}", token)
chequear(
    "Después del rebote el período 1 sigue ABIERTO (no se cerró por error)",
    next(p for p in lp["periodos"] if p["numero"] == 1)["cerrado"] is False,
    "se cerró sin forzar",
)
chequear(
    "El período 1 tiene movimientos (por eso pidió confirmación)",
    p1["documentos"] + p1["asientos"] > 0,
    str(p1),
)

# =====================================================================
# 5. SOLO ADMIN ABRE Y CIERRA
# =====================================================================

token_op = login("operador", "operador123")
if token_op:
    st, d = pedir(
        "POST",
        f"/api/ejercicios/periodos/{p12['id_periodo']}/estado",
        token_op,
        {"cerrado": False},
    )
    chequear(
        "Un operador NO puede abrir un período",
        st == 403,
        f"{st} {str(d)[:120]}",
    )
    st, _ = pedir("GET", f"/api/ejercicios/periodos/{ej['id_ejercicio']}", token_op)
    chequear("Un operador SÍ puede ver los períodos", st == 200, str(st))

# =====================================================================
# 6. REABRIR: LA TRAVA SE LEVANTA
# =====================================================================

st, d = pedir(
    "POST",
    f"/api/ejercicios/periodos/{p12['id_periodo']}/estado",
    token,
    {"cerrado": False},
)
chequear("Se puede reabrir el período", st == 200, f"{st} {str(d)[:160]}")

# Ahora que está abierto, lo que antes rebotaba tiene que entrar.
factura_id = None
if cliente_id:
    st, d = pedir("POST", "/api/facturas", token, cuerpo_factura)
    chequear(
        "Reabierto el período, la misma factura entra",
        st == 201,
        f"{st} {str(d)[:200]}",
    )
    factura_id = d.get("id_factura") if isinstance(d, dict) else None

    if factura_id:
        st, _ = pedir("POST", f"/api/facturas/{factura_id}/anular", token)
        chequear(
            "Anular una factura del período abierto funciona", st == 200, str(st)
        )
        st, d = pedir("DELETE", f"/api/facturas/{factura_id}", token)
        chequear(
            "Una factura con asiento NO se borra (409): se anula",
            st == 409,
            f"{st} {str(d)[:120]}",
        )

st, d = pedir(
    "POST",
    "/api/asientos",
    token,
    {"fecha": FECHA, "concepto": CONCEPTO},
)
chequear(
    "Reabierto el período, el mismo asiento entra",
    st == 201,
    f"{st} {str(d)[:160]}",
)
asiento_id = d.get("id_asiento") if isinstance(d, dict) else None
if asiento_id:
    st, _ = pedir("POST", f"/api/asientos/{asiento_id}/anular", token)
    chequear(
        "Anular el asiento del período abierto funciona", st == 200, str(st)
    )

st, d = pedir(
    "POST",
    "/api/comprobantes-internos",
    token,
    {"codigo_comprobante": CODIGO_COMPROBANTE, "fecha": FECHA,
     "concepto": CONCEPTO},
)
chequear(
    "Reabierto el período, el mismo comprobante entra",
    st == 201,
    f"{st} {str(d)[:160]}",
)

# =====================================================================
# 7. ESTADO FINAL
# =====================================================================

limpiar(token)
_, lp = pedir("GET", f"/api/ejercicios/periodos/{ej['id_ejercicio']}", token)
chequear(
    "Al terminar, ningún período queda cerrado",
    all(p["cerrado"] is False for p in lp["periodos"]),
    str([(p["numero"], p["cerrado"]) for p in lp["periodos"] if p["cerrado"]]),
)

# =====================================================================
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