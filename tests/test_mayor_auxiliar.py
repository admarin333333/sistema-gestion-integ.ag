"""El mayor de una cuenta con auxiliar: nombres, subtotales y filtro por cliente.

    python -X utf8 test_mayor_auxiliar.py

El 02/10/2026 el contador señaló que el mayor de `1.1.03.02 Documentos a
cobrar` mostraba `· CLIENTE` y nada más: con `id_auxiliar: 608` y `609` en
pantalla, no se sabe a quién pertenece cada movimiento. Y el saldo acumulado
mezclaba a todos los clientes, así que el número de la última línea no era el
saldo de nadie.

Lo que se verifica acá:
  1. Cada línea trae `auxiliar_nombre`, no solo el tipo.
  2. Hay un subtotal por auxiliar (debe, haber, saldo, movimientos).
  3. Los subtotales **cubren** el total de la cuenta (si no, algo quedó fuera).
  4. Con `auxiliar_id` el mayor es de UN cliente, y el acumulado es el suyo.
  5. El signo del saldo de cada auxiliar sale de la naturaleza de la cuenta.
  6. Una cuenta SIN auxiliar no trae subtotales (no se inventan).
"""

import json
import os
import sys
import urllib.error
import urllib.request
from decimal import Decimal

BASE = "http://127.0.0.1:8010"
ok = 0
fallos = []
_RUTA_BACKEND = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
)
sys.path.insert(0, _RUTA_BACKEND)

DESDE, HASTA = "2000-01-01", "2100-01-01"


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


from sqlalchemy import text  # noqa: E402

import borrar_prueba  # noqa: E402
from app.database import SessionLocal  # noqa: E402

st, tok = req("POST", "/api/auth/login", {"usuario": "admin", "password": "admin123"})
token = tok.get("access_token")
check("login", st == 200 and token, str(st))

# Limpieza de arranque: lo que dejaron las corridas anteriores y las de las
# suites que corren antes. Esta suite mide SALDOS de la cuenta de documentos a
# cobrar, así que un solo asiento de otra suite la arruina: antes no pasaba
# porque `test_ejercicio.py` —que corre antes por orden alfabético— borraba
# todos los asientos de todos y tapaba la basura de todo el mundo. Ver
# `borrar_prueba.py`.
_db0 = SessionLocal()
borrar_prueba.limpiar_todo(_db0)
_db0.close()

db = SessionLocal()
ids = dict(
    db.execute(
        text("SELECT codigo, id_cuenta FROM plan_cuentas WHERE codigo IN (:d, :c, :i)"),
        {"d": "1.1.03.02", "c": "1.1.03.01", "i": "4.2.01"},
    ).all()
)
DOC_COBRAR = ids.get("1.1.03.02")
CLIENTES_CUENTA = ids.get("1.1.03.01")
INGRESOS = ids.get("4.2.01")
db.close()
check("el plan tiene las cuentas del test", DOC_COBRAR and INGRESOS, str(ids))


def _cargar_factura_prueba(token, id_cuenta_cobrar, cliente_id=None):
    """Carga una factura (que genera su asiento sola) y devuelve qué borrar.

    Hace falta porque el test mira los datos REALES de la cuenta, no unos que
    arma por su cuenta. Si la base está limpia, no hay nada que mirar, así que
    se carga una y al final se borra.

    `cliente_id`: si se pasa, la factura es para ESE cliente. Sirve para dejar
    dos clientes distintos en la cuenta y ver que los saldos se separan.
    """
    from datetime import date

    st, cli = req("GET", "/api/clientes", token=token)
    st, alis = req("GET", "/api/alicuotas-iva", token=token)
    iva = next((a for a in alis if float(a["porcentaje"]) == 21.0), None)

    if cliente_id is not None:
        cliente = next((c for c in cli if c["id"] == cliente_id), None)
    else:
        cliente = next((c for c in cli if c.get("cuit") or c.get("dni")), None)
    if cliente is None:
        print("      (no hay cliente para la factura de prueba)")
        return []

    db = SessionLocal()
    usados = {r[0] for r in db.execute(text("SELECT numero FROM facturas")).all()}
    db.close()
    numero = next(f"{n:08d}" for n in range(800, 899) if f"{n:08d}" not in usados)

    st, f = req("POST", "/api/facturas", {
        "cliente_id": cliente["id"],
        "tipo_comprobante": "factura_b",
        "punto_venta": "0001",
        "numero": numero,
        "fecha": date.today().isoformat(),
        "importe": 121000.00,
        "condicion_venta": "cta_corriente_30",
        "tipo_operacion": "SERVICIOS",
        "alicuota_iva_id": iva["id"] if iva else None,
        "concepto": "Mayor auxiliar — prueba",
    }, token=token)
    if st != 201:
        print(f"      (no se pudo cargar la factura de prueba: {st})")
        return []
    return [f["id"]]


def _otro_cliente(token, excluir_id=None):
    """Un cliente que NO sea el que ya está en la cuenta.

    Hace falta para el caso de dos: si las dos facturas fueran del mismo
    cliente, Documentos a cobrar seguiría teniendo un solo auxiliar y los saldos
    no se verían separados.
    """
    st, cli = req("GET", "/api/clientes", token=token)
    otros = [c for c in cli if c["id"] != excluir_id and (c.get("cuit") or c.get("dni"))]
    return otros[0]["id"] if otros else None


def _borrar_facturas(ids):
    """Borra las facturas que creó este test, con su asiento.

    Con asiento no se borran por la API (409, a propósito), y `DELETE FROM
    asientos` a secas se lleva los de los demás: va acotado a lo nuestro.
    """
    if not ids:
        return
    db = SessionLocal()
    try:
        for fid in ids:
            aid = db.execute(
                text("SELECT id_asiento FROM asiento_origen WHERE id_factura = :f"),
                {"f": fid},
            ).scalar()
            if aid is not None:
                for sql in ("DELETE FROM asiento_detalle WHERE id_asiento = :a",
                            "DELETE FROM asiento_origen WHERE id_asiento = :a",
                            "DELETE FROM asientos WHERE id_asiento = :a"):
                    db.execute(text(sql), {"a": aid})
            db.execute(text("DELETE FROM facturas WHERE id = :f"), {"f": fid})
        db.commit()
    finally:
        db.close()

# =====================================================================
print("\n== 1. El mayor de Documentos a cobrar, con auxiliar ==")

st, m = req("GET", f"/api/mayores/{DOC_COBRAR}?desde={DESDE}&hasta={HASTA}", token=token)
check("responde 200", st == 200, f"{st} {str(m)[:120]}")
check("la cuenta dice que usa auxiliar CLIENTE",
      m["cuenta"]["tipo_auxiliar"] == "CLIENTE", str(m["cuenta"]["tipo_auxiliar"]))

# Ojo: este test NO crea sus propios asientos. Lee los que haya en la base, así
# que cuando se corre después de otro que limpia los asientos (motor_contable,
# por ejemplo) se encuentra con la cuenta en cero. Por eso, si no hay nada, se
# carga una factura de prueba y se borra al final: el test tiene que servir
# con la base llena Y con la base vacía.
if m["movimientos"] == 0:
    print("\n  (la cuenta está en cero: se carga una factura de prueba)")
    borrar = _cargar_factura_prueba(token, DOC_COBRAR)
    st, m = req("GET", f"/api/mayores/{DOC_COBRAR}?desde={DESDE}&hasta={HASTA}",
                token=token)
    check("con la factura de prueba hay movimientos", m["movimientos"] > 0,
          str(m["movimientos"]))
else:
    borrar = []

print("\n== 2. Cada línea trae el NOMBRE del auxiliar, no solo el tipo ==")
con_aux = [l for l in m["lineas"] if l["tipo_auxiliar"]]
check("hay líneas con auxiliar", len(con_aux) > 0, str(len(con_aux)))
check("todas traen auxiliar_nombre",
      all(l["auxiliar_nombre"] for l in con_aux),
      str([l["auxiliar_nombre"] for l in con_aux if not l["auxiliar_nombre"]]))
check("el nombre NO es un número pelado (sigue siendo 'CLIENTE')",
      all("CLIENTE" not in (l["auxiliar_nombre"] or "") for l in con_aux),
      str([l["auxiliar_nombre"] for l in con_aux]))
check("el nombre trae el nro de cuenta, para no confundir dos homónimos",
      all("cuenta" in (l["auxiliar_nombre"] or "") for l in con_aux),
      str([l["auxiliar_nombre"] for l in con_aux]))

# =====================================================================
print("\n== 3. Los subtotales por auxiliar ==")
check("trae la lista de auxiliares", len(m["auxiliares"]) > 0, str(len(m["auxiliares"])))
for a in m["auxiliares"]:
    print(f"      {a['nombre']:<42} debe={a['debe']:>12} haber={a['haber']:>10} "
          f"saldo={a['saldo']:>12} ({a['movimientos']} mov)")
    check(f"  {a['nombre']}: el saldo es debe - haber (es DEUDORA)",
          Decimal(str(a["saldo"])) == Decimal(str(a["debe"])) - Decimal(str(a["haber"])),
          f"{a['saldo']} vs {a['debe']}-{a['haber']}")
    check(f"  {a['nombre']}: al menos un movimiento", a["movimientos"] > 0,
          str(a["movimientos"]))

print("\n== 4. Los subtotales tienen que CUBRIR el total de la cuenta ==")
# Si no dan igual que el total, algún movimiento se quedó sin agrupar y el
# contador vería un reparto que no cierra.
check("la suma de los subtotales = el total de la cuenta",
      Decimal(str(m["auxiliares_cubren"])) == Decimal(str(m["total_debe"])),
      f"{m['auxiliares_cubren']} vs {m['total_debe']}")
check("y la suma de los movimientos por auxiliar = el total de la cuenta",
      sum(a["movimientos"] for a in m["auxiliares"]) == m["movimientos"],
      f"{sum(a['movimientos'] for a in m['auxiliares'])} vs {m['movimientos']}")
check("y coincide con el saldo final de la cuenta",
      sum((Decimal(str(a["saldo"])) for a in m["auxiliares"]), Decimal("0"))
      == Decimal(str(m["saldo_final"])),
      str([a["saldo"] for a in m["auxiliares"]]))
check("el acumulado de las líneas cierra (el control `cierra`)",
      m["cierra"] is True, str(m["cierra"]))

# =====================================================================
print("\n== 5. Filtrar por UN auxiliar: el acumulado es de ese cliente ==")
# El punto de todo esto: el saldo de la cuenta COMPLETO mezcla clientes.
# Con el filtro, el número final tiene que ser el de ese cliente solo.
alfa = max(m["auxiliares"], key=lambda a: a["saldo"])
print(f"\n  Mirando a: {alfa['nombre']} (debe {alfa['debe']})")

st, uno = req("GET", f"/api/mayores/{DOC_COBRAR}?desde={DESDE}&hasta={HASTA}"
                     f"&auxiliar_id={alfa['id_auxiliar']}", token=token)
check("responde 200", st == 200, f"{st} {str(uno)[:120]}")
check("dice qué auxiliar está mirando",
      uno["auxiliar_nombre"] == alfa["nombre"],
      f"{uno.get('auxiliar_nombre')} vs {alfa['nombre']}")
check("solo trae los movimientos de ESE cliente",
      all(l["id_auxiliar"] == alfa["id_auxiliar"] for l in uno["lineas"]),
      str([l["id_auxiliar"] for l in uno["lineas"]]))
check("y son los mismos que el subtotal decía",
      uno["movimientos"] == alfa["movimientos"],
      f"{uno['movimientos']} vs {alfa['movimientos']}")
check("el total de debe es el del subtotal",
      Decimal(str(uno["total_debe"])) == Decimal(str(alfa["debe"])),
      f"{uno['total_debe']} vs {alfa['debe']}")
check("el SALDO FINAL es el de ese cliente, no el de la cuenta entera",
      Decimal(str(uno["saldo_final"])) == Decimal(str(alfa["saldo"])),
      f"{uno['saldo_final']} vs {alfa['saldo']}")
# Con un solo auxiliar los dos números dan igual, así que no se puede afirmar
# que sea "menor": la diferencia se ve recién cuando hay más de un cliente. Lo
# que sí tiene que ser cierto siempre es que el saldo del auxiliar sea el del
# subtotal (el check de arriba), y no el de la cuenta mezclada.

print("\n== 5b. Con DOS clientes, cada saldo es el suyo y NO el de la cuenta ==")
# Este es el caso que motivó el cambio: con dos clientes, el saldo de la cuenta
# es la suma de los dos y no significa nada. Cada uno tiene que ver lo suyo.
if len(m["auxiliares"]) < 2:
    print("      (hace falta un segundo cliente en la cuenta)")
    # Para que el caso sirva tiene que ser OTRO cliente: si se cargara otra
    # factura al mismo, seguiría habiendo un solo auxiliar y no se probaría nada.
    otro = _otro_cliente(token, m["auxiliares"][0]["id_auxiliar"] if m["auxiliares"] else None)
    borrar2 = _cargar_factura_prueba(token, DOC_COBRAR, cliente_id=otro)
    borrar = list(dict.fromkeys(borrar + borrar2))
    st, m = req("GET", f"/api/mayores/{DOC_COBRAR}?desde={DESDE}&hasta={HASTA}",
                token=token)

if len(m["auxiliares"]) >= 2:
    a1, a2 = m["auxiliares"][0], m["auxiliares"][1]
    total_cuenta = Decimal(str(m["saldo_final"]))
    suma = Decimal(str(a1["saldo"])) + Decimal(str(a2["saldo"]))
    print(f"      {a1['nombre']}: {a1['saldo']}")
    print(f"      {a2['nombre']}: {a2['saldo']}")
    print(f"      la cuenta entera: {total_cuenta}")
    check("el saldo de la cuenta es la SUMA de los dos clientes",
          suma == total_cuenta, f"{suma} vs {total_cuenta}")
    check("cada saldo es menor que el de la cuenta (estaban mezclados)",
          Decimal(str(a1["saldo"])) < total_cuenta
          and Decimal(str(a2["saldo"])) < total_cuenta,
          f"{a1['saldo']} / {a2['saldo']} vs {total_cuenta}")

    for etiqueta, aux in (("el primero", a1), ("el segundo", a2)):
        st, uno = req("GET", f"/api/mayores/{DOC_COBRAR}?desde={DESDE}&hasta={HASTA}"
                             f"&auxiliar_id={aux['id_auxiliar']}", token=token)
        check(f"filtrando por {etiqueta} ({aux['nombre']}), el saldo es SUYO",
              Decimal(str(uno["saldo_final"])) == Decimal(str(aux["saldo"]))
              and uno["saldo_final"] != total_cuenta,
              f"{uno['saldo_final']} vs {aux['saldo']} (cuenta: {total_cuenta})")
else:
    print("      (no se pudieron dejar dos clientes: el caso de dos se omite)")
check("cierra", uno["cierra"] is True, str(uno["cierra"]))
# Con el filtro puesto, el bloque de subtotales sobra: es ruido.
check("con el filtro puesto NO repite los subtotales",
      len(uno["auxiliares"]) == 0, str(len(uno["auxiliares"])))

print("\n== 6. Un auxiliar que no existe en esa cuenta ==")
st, ninguno = req("GET", f"/api/mayores/{DOC_COBRAR}?desde={DESDE}&hasta={HASTA}"
                         f"&auxiliar_id=999999", token=token)
check("responde 200 con 0 movimientos (no inventa)", st == 200 and ninguno["movimientos"] == 0,
      f"{st} {ninguno.get('movimientos')}")
check("el total es 0", Decimal(str(ninguno["saldo_final"])) == Decimal("0"),
      str(ninguno["saldo_final"]))
# Un auxiliar que no existe NO puede tener nombre: si acá saliera algo, el
# sistema estaría inventando un cliente. Mejor `None`, y que la pantalla lo
# muestre como "Auxiliar 999999" o avise.
check("y NO inventa un nombre para un auxiliar inexistente",
      ninguno["auxiliar_nombre"] is None, str(ninguno.get("auxiliar_nombre")))

# =====================================================================
print("\n== 7. Una cuenta SIN auxiliar no trae subtotales ==")
st, ing = req("GET", f"/api/mayores/{INGRESOS}?desde={DESDE}&hasta={HASTA}", token=token)
check("responde 200", st == 200, f"{st} {str(ing)[:120]}")
# Ojo: el plan de cuentas usa el TEXTO "NINGUNO", no NULL. Una cuenta sin
# auxiliar tiene `tipo_auxiliar = 'NINGUNO'`, y eso no cuenta como auxiliar.
check("no tiene auxiliar (el plan usa el texto 'NINGUNO')",
      ing["cuenta"]["tipo_auxiliar"] in (None, "", "NINGUNO"),
      str(ing["cuenta"]["tipo_auxiliar"]))
check("y no trae lista de auxiliares", ing["auxiliares"] == [], str(ing["auxiliares"]))
check("pero el saldo sigue saliendo", ing["cierra"] is True, str(ing["cierra"]))
if ing["movimientos"] == 0:
    print("      (sin movimientos en esta base)")

# =====================================================================
print("\n== 8. Una cuenta que no existe ==")
st, r = req("GET", "/api/mayores/999999", token=token)
check("da 404, no un error raro", st == 404, str(st))

# =====================================================================
print("\n== 9. Clientes (1.1.03.01) también es cuenta de cliente ==")
if CLIENTES_CUENTA:
    st, cl = req("GET", f"/api/mayores/{CLIENTES_CUENTA}?desde={DESDE}&hasta={HASTA}",
                 token=token)
    check("responde 200", st == 200, f"{st} {str(cl)[:120]}")
    check("es de tipo CLIENTE", cl["cuenta"]["tipo_auxiliar"] == "CLIENTE",
          str(cl["cuenta"]["tipo_auxiliar"]))
    if cl["movimientos"] == 0:
        print("      (sin movimientos: no hay subtotales que verificar)")
    else:
        check("si tiene movimientos, trae subtotales que cubren el total",
              Decimal(str(cl["auxiliares_cubren"])) == Decimal(str(cl["total_debe"])),
              f"{cl['auxiliares_cubren']} vs {cl['total_debe']}")

# =====================================================================
print("\n== 10. Limpiar lo que este test cargó ==")
# Si se cargó una factura de prueba porque la base estaba vacía, se borra y la
# base queda como estaba. Si no se cargó nada, no hay que borrar.
if borrar:
    _borrar_facturas(borrar)
    st, m2 = req("GET", f"/api/mayores/{DOC_COBRAR}?desde={DESDE}&hasta={HASTA}",
                 token=token)
    check("la factura de prueba se borró y la cuenta volvió a cero",
          m2["movimientos"] == 0, str(m2["movimientos"]))
    check("y el total quedó en cero", Decimal(str(m2["saldo_final"])) == Decimal("0"),
          str(m2["saldo_final"]))
else:
    print("      (no se cargó nada: no hay que borrar)")

st, cg = req("GET", "/api/control-general", token=token)
check("el control general sigue ok", cg["ok"] is True, str(cg["problemas"])[:200])

print(f"\n{ok} OK / {len(fallos)} fallos")
if fallos:
    raise SystemExit(1)