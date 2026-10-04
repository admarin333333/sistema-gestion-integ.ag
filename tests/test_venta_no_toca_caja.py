"""La venta va SIEMPRE a Documentos a cobrar, y Caja es de tesorería.

    python -X utf8 test_venta_no_toca_caja.py

Esta regla la pidió el contador el 02/10/2026 y es fácil de romper sin
darse cuenta: hace un rato `migrar_asientos_automaticos.py` sembraba las
ventas al contado con Caja en el Debe, y los tests también lo afirmaban, así
que todo daba verde con la cuenta equivocada.

Este test mira la cosa de dos lados:

  1. **La configuración**: en `config_asientos`, las 4 filas de venta tienen
     `cuenta_debe` = Documentos a cobrar. Si alguien cambia ese dato, salta acá
     antes de que se cuelgue una factura con la cuenta mal.
  2. **Los asientos de verdad**: ninguno de los asientos que nacieron de una
     factura toca `1.1.01.01 Caja`. Crea una factura al contado y otra a
     cuenta corriente y revisa las dos.

Caja y Fondo fijo son cuentas de **tesorería**: la plata entra ahí recién
cuando se registra el cobro de la factura.
"""

import json
import os
import sys
import urllib.error
import urllib.request
# La dirección de la API sale de `GC_BASE_URL` para poder correr estas pruebas
# contra la base de PRUEBAS y no contra la del estudio. Si la variable no
# está, usa 8010 como antes: no cambia cómo se corren.

BASE = os.environ.get("GC_BASE_URL", "http://127.0.0.1:8010")
ok = 0
fallos = []
_RUTA_BACKEND = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
)
sys.path.insert(0, _RUTA_BACKEND)

CAJA = "1.1.01.01"
FONDO_FIJO = "1.1.01.02"
DOC_COBRAR = "1.1.03.02"
CUENTAS_DE_COBRO = (CAJA, FONDO_FIJO)


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


st, tok = req("POST", "/api/auth/login", {"usuario": "admin", "password": "admin123"})
token = tok.get("access_token")
check("login", st == 200 and token, str(st))

# =====================================================================
print("\n== 1. La configuración: las 4 ventas van a Documentos a cobrar ==")

from sqlalchemy import text  # noqa: E402

# Esta suite habla con la base de DOS maneras: por HTTP (`BASE`) y por SQL
# directo (`app.database`, para limpiar lo que dejó la corrida). Con solo
# `GC_BASE_URL` el SQL se va a la base REAL y la limpieza no borra nada de la base
# de pruebas.
#
# `DB_NAME` tiene que estar puesta ANTES de que se importe `app.database`, porque
# ese módulo lee el entorno UNA sola vez al importarse. Por eso este bloque va
# arriba del archivo, en el nivel del módulo, y no adentro de la función que
# limpia.
if "GC_BASE_URL" in os.environ:
    os.environ.setdefault(
        "DB_NAME", os.environ.get("GC_TEST_DB", "gestion_contable_test")
    )

from app.database import SessionLocal  # noqa: E402

db = SessionLocal()
cfg = {
    r["clave"]: r
    for r in db.execute(
        text(
            "SELECT c.clave, p.codigo, c.cuenta_haber_ingresos, hi.codigo AS ing "
            "  FROM config_asientos c "
            "  LEFT JOIN plan_cuentas p ON p.id_cuenta = c.cuenta_debe "
            "  LEFT JOIN plan_cuentas hi ON hi.id_cuenta = c.cuenta_haber_ingresos "
            " WHERE c.clave LIKE 'VENTA_%' AND c.activa = 1"
        )
    ).mappings()
}
db.close()

CLAVES = [
    "VENTA_SERVICIOS_CONTADO",
    "VENTA_SERVICIOS_CTA_CORRIENTE",
    "VENTA_ARTICULOS_CONTADO",
    "VENTA_ARTICULOS_CTA_CORRIENTE",
]
check("están las 4 ventas configuradas", len(cfg) == 4, str(sorted(cfg)))
for clave in CLAVES:
    c = cfg.get(clave)
    check(f"{clave}: el Debe va a {DOC_COBRAR}",
          c is not None and c["codigo"] == DOC_COBRAR,
          str(c["codigo"]) if c else "no existe")
    check(f"{clave}: NO va a Caja ni a Fondo fijo",
          c is not None and c["codigo"] not in CUENTAS_DE_COBRO,
          str(c["codigo"]) if c else "no existe")

# El Haber de ingresos tiene que seguir distinguiendo servicios de artículos:
# aunque el Debe sea el mismo, esto no se mezcló.
check("servicios siguen yendo a ingresos por servicios (4.2.01)",
      cfg.get("VENTA_SERVICIOS_CONTADO", {}).get("ing") == "4.2.01",
      str(cfg.get("VENTA_SERVICIOS_CONTADO")))
check("artículos siguen yendo a ventas artículos (4.1.01)",
      cfg.get("VENTA_ARTICULOS_CONTADO", {}).get("ing") == "4.1.01",
      str(cfg.get("VENTA_ARTICULOS_CONTADO")))

# =====================================================================
print("\n== 2. Los asientos ya guardados: ninguno toca Caja ==")

db = SessionLocal()
malos = db.execute(
    text(
        "SELECT o.id_factura, o.id_asiento, p.codigo "
        "  FROM asiento_origen o "
        "  JOIN asiento_detalle d ON d.id_asiento = o.id_asiento "
        "  JOIN plan_cuentas p ON p.id_cuenta = d.id_cuenta "
        " WHERE o.origen = 'FACTURA' AND p.codigo IN ('1.1.01.01','1.1.01.02')"
    )
).mappings().all()
cuantas = db.execute(
    text(
        "SELECT COUNT(DISTINCT o.id_asiento) "
        "  FROM asiento_origen o "
        " WHERE o.origen = 'FACTURA'"
    )
).scalar()
db.close()

check(f"los {cuantas} asientos de factura NO tocan Caja ni Fondo fijo",
      not malos, str([dict(m) for m in malos]))

# =====================================================================
print("\n== 3. Dos facturas nuevas, una al contado y otra a cuenta corriente ==")

st, cli = req("GET", "/api/clientes", token=token)
clientes = [c for c in cli if c.get("cuit") or c.get("dni")]
check("hay un cliente para probar", bool(clientes), "no hay clientes")
CLIENTE = clientes[0]["id"] if clientes else None

# Ojo: el nombre de la alícuota viene con coma decimal ("IVA 21%"), así que se
# busca por el PORCENTAJE, que es un número y no se puede leer mal.
st, alis = req("GET", "/api/alicuotas-iva", token=token)
IVA21 = next((a for a in alis if float(a["porcentaje"]) == 21.0), None)
check("hay alícuota de 21%", IVA21 is not None, str(alis)[:120])

# El tipo de comprobante va en minúsculas con guion bajo ("factura_b"). El
# backend lo valida contra TIPOS_COMPROBANTE y corta con 422 si no coincide.
TIPO_COMPROBANTE = "factura_b"

# Número de factura libre: se busca uno que no exista.
db = SessionLocal()
usados = {r[0] for r in db.execute(text("SELECT numero FROM facturas")).all()}
db.close()
NUEVO = next(f"{n:08d}" for n in range(900, 999) if f"{n:08d}" not in usados)


def crear(condicion, numero):
    st, pre = req("POST", "/api/facturas/preview-asiento", {
        "cliente_id": CLIENTE,
        "tipo_comprobante": TIPO_COMPROBANTE,
        "punto_venta": "0001",
        "numero": numero,
        "fecha": "2026-10-02",
        "importe": 121000.00,
        "condicion_venta": condicion,
        "tipo_operacion": "SERVICIOS",
        "alicuota_iva_id": IVA21["id"] if IVA21 else None,
        "concepto": f"Prueba caja {condicion}",
    }, token=token)
    check(f"el preview de la factura al {condicion} responde 200", st == 200,
          f"{st} {str(pre)[:150]}")

    codigos = [l["codigo"] for l in pre["lineas"]]
    debe = [l for l in pre["lineas"] if float(l["debe"]) > 0]
    check(f"al {condicion}: el Debe va a {DOC_COBRAR}",
          len(debe) == 1 and debe[0]["codigo"] == DOC_COBRAR,
          str(codigos))
    check(f"al {condicion}: no aparece Caja ni Fondo fijo",
          not (set(codigos) & set(CUENTAS_DE_COBRO)), str(codigos))
    check(f"al {condicion}: el Debe lleva el cliente como auxiliar",
          debe and debe[0].get("tipo_auxiliar") == "CLIENTE"
          and debe[0].get("id_auxiliar") == CLIENTE,
          str(debe[0] if debe else None))
    check(f"al {condicion}: el preview cierra (debe = haber)",
          float(pre["total_debe"]) == float(pre["total_haber"]),
          f"{pre['total_debe']} vs {pre['total_haber']}")

    st, f = req("POST", "/api/facturas", {
        "cliente_id": CLIENTE,
        "tipo_comprobante": TIPO_COMPROBANTE,
        "punto_venta": "0001",
        "numero": numero,
        "fecha": "2026-10-02",
        "importe": 121000.00,
        "condicion_venta": condicion,
        "tipo_operacion": "SERVICIOS",
        "alicuota_iva_id": IVA21["id"] if IVA21 else None,
        "concepto": f"Prueba caja {condicion}",
    }, token=token)
    check(f"la factura al {condicion} se guardó", st == 201, f"{st} {str(f)[:150]}")
    return f


f_contado = crear("contado", NUEVO)
f_cta = crear("cta_corriente_30", f"{int(NUEVO) + 1:08d}")

# El asiento REAL tiene que coincidir con el preview (misma función).
for etiqueta, f in (("contado", f_contado), ("cta corriente", f_cta)):
    if not f or "id_asiento" not in f:
        check(f"el asiento real de la factura al {etiqueta} existe", False, str(f)[:150])
        continue
    st, a = req("GET", f"/api/asientos/{f['id_asiento']}", token=token)
    codigos = [d["codigo"] for d in a["detalle"]]
    check(f"el asiento real al {etiqueta} va a {DOC_COBRAR}",
          DOC_COBRAR in codigos, str(codigos))
    check(f"el asiento real al {etiqueta} NO toca Caja",
          not (set(codigos) & set(CUENTAS_DE_COBRO)), str(codigos))
    check(f"el asiento real al {etiqueta} está contabilizado",
          a["estado"] == "CONTABILIZADO", str(a["estado"]))
    check(f"el asiento real al {etiqueta} cierra",
          float(a["total_debe"]) == float(a["total_haber"]),
          f"{a['total_debe']} vs {a['total_haber']}")

# =====================================================================
print("\n== 4. Limpiar: borrar SOLO las dos facturas de este test ==")

# Con asiento no se borran por la API (409, a propósito). Y no se hace
# `DELETE FROM asientos` a secas, que en una base con asientos reales los borra
# todos: acá se borra SOLO lo que creó este test, y en el orden que piden las
# claves foráneas (detalle → origen → asientos → facturas).
db = SessionLocal()
ids = [f["id"] for f in (f_contado, f_cta) if f and "id" in f]
borrados = 0
try:
    for fid in ids:
        aid = db.execute(
            text("SELECT id_asiento FROM asiento_origen WHERE id_factura = :f"),
            {"f": fid},
        ).scalar()
        if aid is not None:
            db.execute(text("DELETE FROM asiento_detalle WHERE id_asiento = :a"), {"a": aid})
            db.execute(text("DELETE FROM asiento_origen WHERE id_asiento = :a"), {"a": aid})
            db.execute(text("DELETE FROM asientos WHERE id_asiento = :a"), {"a": aid})
        n = db.execute(text("DELETE FROM facturas WHERE id = :f"), {"f": fid}).rowcount
        borrados += n
    db.commit()
finally:
    db.close()
check("las dos facturas de prueba se borraron", borrados == 2, str(borrados))

st, cg = req("GET", "/api/control-general", token=token)
check("el control general sigue ok", cg["ok"] is True, str(cg["problemas"])[:200])

print(f"\n{ok} OK / {len(fallos)} fallos")
if fallos:
    raise SystemExit(1)