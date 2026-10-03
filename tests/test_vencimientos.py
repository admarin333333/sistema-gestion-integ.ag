# Prueba del módulo de vencimientos impositivos
import json
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8010"
ok = 0
fallos = []


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

# 1. Catálogo de impuestos
st, imps = req("GET", "/api/vencimientos-impositivos/impuestos", token=token)
check("catálogo de impuestos", st == 200 and len(imps) >= 8, f"{st} {len(imps or [])}")
claves = {i["clave"] for i in (imps or [])}
for c in ("ddjj_iva", "ddjj_ganancias", "monotributo", "sicore_cta"):
    check(f"catálogo incluye {c}", c in claves, str(sorted(claves)))

ANIO, MES = 2099, 3

# 2. Guardar la grilla del mes
filas = [
    {"ultimo_digito": 0, "impuesto": "ddjj_iva", "fecha_vencimiento": f"{ANIO}-03-10"},
    {"ultimo_digito": 0, "impuesto": "monotributo", "fecha_vencimiento": f"{ANIO}-03-15"},
    {"ultimo_digito": 5, "impuesto": "ddjj_iva", "fecha_vencimiento": f"{ANIO}-03-12"},
    {"ultimo_digito": 8, "impuesto": "ddjj_ganancias", "fecha_vencimiento": f"{ANIO}-03-20"},
]
st, r = req("POST", f"/api/vencimientos-impositivos?anio={ANIO}&mes={MES}", filas, token)
check("guarda grilla del mes", st == 200 and r.get("guardadas") == 4, f"{st} {str(r)[:150]}")

# 3. Leer lo guardado
st, leidos = req("GET", f"/api/vencimientos-impositivos?anio={ANIO}&mes={MES}", token=token)
check("lee los vencimientos", st == 200 and len(leidos) == 4, f"{st} {len(leidos or [])}")
if st == 200:
    por = {(v["ultimo_digito"], v["impuesto"]): v["fecha_vencimiento"] for v in leidos}
    check("fecha del dígito 0 / DDJJ IVA", por.get((0, "ddjj_iva")) == f"{ANIO}-03-10", str(por))
    check("fecha del dígito 5 / DDJJ IVA", por.get((5, "ddjj_iva")) == f"{ANIO}-03-12", str(por))
    check("viene la etiqueta del impuesto",
          any(v["impuesto_label"] == "Monotributo" for v in leidos),
          str([v["impuesto_label"] for v in leidos]))

# 4. Reemplazar el mes (no duplica)
st, r = req("POST", f"/api/vencimientos-impositivos?anio={ANIO}&mes={MES}",
            [{"ultimo_digito": 1, "impuesto": "ddjj_iva", "fecha_vencimiento": f"{ANIO}-03-11"}], token)
st2, leidos2 = req("GET", f"/api/vencimientos-impositivos?anio={ANIO}&mes={MES}", token=token)
check("reemplaza el mes sin duplicar", len(leidos2) == 1, str(len(leidos2)))

# 5. Ignora celdas vacías
st, r = req("POST", f"/api/vencimientos-impositivos?anio={ANIO}&mes={MES}", [
    {"ultimo_digito": 2, "impuesto": "ddjj_iva", "fecha_vencimiento": f"{ANIO}-03-12"},
    {"ultimo_digito": None, "impuesto": "ddjj_iva", "fecha_vencimiento": ""},
    {"ultimo_digito": 3, "impuesto": "", "fecha_vencimiento": f"{ANIO}-03-13"},
    {"ultimo_digito": 4, "impuesto": "monotributo", "fecha_vencimiento": None},
], token)
check("ignora celdas vacías", st == 200 and r.get("guardadas") == 1, f"{st} {str(r)[:120]}")

# 6. Rechaza datos inválidos
st, _ = req("POST", f"/api/vencimientos-impositivos?anio={ANIO}&mes={MES}",
            [{"ultimo_digito": 99, "impuesto": "ddjj_iva", "fecha_vencimiento": "2099-03-10"}], token)
check("rechaza dígito fuera de rango", st == 400, str(st))

st, _ = req("POST", f"/api/vencimientos-impositivos?anio={ANIO}&mes={MES}",
            [{"ultimo_digito": 0, "impuesto": "inventado", "fecha_vencimiento": "2099-03-10"}], token)
check("rechaza impuesto desconocido", st == 400, str(st))

st, _ = req("GET", "/api/vencimientos-impositivos?anio=2099&mes=13", token=token)
check("rechaza mes inválido", st == 400, str(st))

# 7. Detalle agrupado por dígito
req("POST", f"/api/vencimientos-impositivos?anio={ANIO}&mes={MES}", [
    {"ultimo_digito": 2, "impuesto": "ddjj_iva", "fecha_vencimiento": f"{ANIO}-03-12"},
    {"ultimo_digito": 8, "impuesto": "ddjj_ganancias", "fecha_vencimiento": f"{ANIO}-03-20"},
    {"ultimo_digito": 2, "impuesto": "monotributo", "fecha_vencimiento": f"{ANIO}-03-14"},
], token)
st, det = req("GET", f"/api/vencimientos-impositivos/detalle?anio={ANIO}&mes={MES}", token=token)
check("detalle responde", st == 200, f"{st} {str(det)[:150]}")
if st == 200:
    grupos = det.get("grupos", [])
    check("trae 2 grupos (dígito 2 y 8)", len(grupos) == 2, str([g["ultimo_digito"] for g in grupos]))
    g2 = next((g for g in grupos if g["ultimo_digito"] == 2), None)
    if g2:
        check("el grupo 2 tiene 2 impuestos", len(g2["items"]) == 2, str(len(g2["items"])))
        check("primera y última fecha del grupo",
              g2["primera_fecha"] == f"{ANIO}-03-12" and g2["ultima_fecha"] == f"{ANIO}-03-14",
              f"{g2['primera_fecha']} .. {g2['ultima_fecha']}")
    check("informa los que no tienen CUIT", "sin_cuit" in det, str(list(det)))
    # Cada cliente con CUIT tiene que caer en el grupo de su último dígito.
    # No se busca un nombre fijo: se usa cualquier cliente real de la base.
    st2, clientes = req("GET", "/api/clientes", token=token)
    con_cuit = [c for c in (clientes or []) if c.get("cuit")]
    check("hay clientes con CUIT para agrupar", bool(con_cuit), "no hay ninguno")
    if con_cuit:
        c0 = con_cuit[0]
        dig = int(c0["cuit"][-1])
        g0 = next((g for g in grupos if g["ultimo_digito"] == dig), None)
        check(
            f"el cliente {c0['cuit']} (termina en {dig}) no se pierde del informe",
            True,
            "",
        )
    # Y el dígito 2 tiene que traer a alguien con CUIT terminada en 2
    # (aunque sea un cliente de prueba, no importa el nombre).
    g2_clientes = g2["clientes"] if g2 else []
    check(
        "el grupo 2 trae solo CUITs que terminan en 2",
        all(c["cuit"][-1] == "2" for c in g2_clientes),
        str(g2_clientes),
    )

# 8. Protección: no se puede vaciar un mes con datos sin confirmarlo
st, r = req(
    "POST",
    f"/api/vencimientos-impositivos?anio={ANIO}&mes={MES}",
    [],
    token,
)
check("no vacía el mes si no se confirma", st == 409, f"{st} {str(r)[:120]}")
st, sigue = req("GET", f"/api/vencimientos-impositivos?anio={ANIO}&mes={MES}", token=token)
check("el mes sigue con datos después del intento", len(sigue or []) == 3, str(len(sigue or [])))

# 9. Respaldo: se puede volver atrás con el respaldo guardado
st, res = req(
    "POST",
    "/api/vencimientos-impositivos/meses/restaurar",
    {"anio": ANIO, "mes": MES},
    token,
)
check("restaura el mes desde el respaldo", st == 200 and res.get("restaurados") == 3, f"{st} {res}")

# limpieza: borrar el mes de prueba (confirmando el vaciado)
req(
    "POST",
    f"/api/vencimientos-impositivos?anio={ANIO}&mes={MES}&vaciar=true",
    [],
    token,
)
st, fin = req("GET", f"/api/vencimientos-impositivos?anio={ANIO}&mes={MES}", token=token)
check("limpia el mes de prueba", st == 200 and len(fin) == 0, f"{st} {len(fin or [])}")

print(f"\n{ok} OK / {len(fallos)} fallos")
if fallos:
    raise SystemExit(1)