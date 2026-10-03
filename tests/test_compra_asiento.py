"""El asiento de una COMPRA (factura de proveedor).

La compra ya no elige centro de costos ni tipo de gasto: elige UNA cuenta del
plan de cuentas (6.1.03 luz-agua), y de esa cuenta sale el centro. Eso es lo que
verifica esta suite:

  - la cuenta elegida tiene que ser imputable y estar bajo 6 (GASTOS);
  - el asiento tiene las CUATRO líneas con las cuentas y los signos correctos;
  - el Haber de Proveedores es el total de la compra;
  - una NOTA DE CRÉDITO del proveedor es el mismo asiento al revés;
  - la compra guardada NO mueve la cuenta hasta que se asienta (y después sí);
  - una compra con asiento no se borra (409);
  -preview y el asiento real usan la misma función.

Al final borra todo lo que creó (por SQL: los asientos con comprobante propio no
se pueden borrar por la API).
"""

import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8010"
resultado = []

MARCA = "PRUEBA COMPRA ASIENTO"


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
        crudo = e.read().decode()
        try:
            return e.code, json.loads(crudo)
        except Exception:
            return e.code, crudo[:300]


def chequear(nombre, condicion, detalle=""):
    resultado.append((nombre, bool(condicion), detalle))


def linea_por_codigo(lineas, codigo):
    for l in lineas:
        if l["codigo"] == codigo:
            return l
    return None


def suma(l, campo):
    return float(l[campo] or 0)


def limpiar(tok, compras, asientos):
    """Las compras primero: `asiento_origen.id_compra` es ON DELETE RESTRICT, y
    los asientos con comprobante propio tampoco se borran por API."""
    sys.path.insert(0, r"C:\proyecto-gestion-contable\backend")
    from sqlalchemy import text

    from app.database import SessionLocal

    db = SessionLocal()
    if compras:
        db.execute(
            text(
                "DELETE FROM asiento_origen WHERE origen='COMPRA' AND id_compra IN ("
                + ",".join(str(c) for c in compras)
                + ")"
            )
        )
    if asientos:
        m = ",".join(str(a) for a in asientos)
        comps = [
            f[0]
            for f in db.execute(
                text(
                    "SELECT id_comprobante FROM asientos WHERE id_asiento IN ("
                    + m
                    + ")"
                )
            ).all()
        ]
        # El comprobante va DESPUÉS del asiento: es ON DELETE RESTRICT.
        db.execute(text("DELETE FROM asiento_detalle WHERE id_asiento IN (" + m + ")"))
        db.execute(text("DELETE FROM asientos WHERE id_asiento IN (" + m + ")"))
        if comps:
            db.execute(
                text(
                    "DELETE FROM comprobantes_internos WHERE id_comprobante IN ("
                    + ",".join(str(c) for c in comps)
                    + ")"
                )
            )
    if compras:
        db.execute(
            text("DELETE FROM compras WHERE id IN (" + ",".join(str(c) for c in compras) + ")")
        )
    db.commit()
    db.close()


tok = pedir("POST", "/api/auth/login",
            cuerpo={"usuario": "admin", "password": "admin123"})[1]["access_token"]

# --- datos de prueba ----------------------------------------------------
codigo, proveedores = pedir("GET", "/api/proveedores", tok)
if not proveedores:
    raise SystemExit("no hay proveedores para probar")
prov = proveedores[0]

codigo, alicuotas = pedir("GET", "/api/alicuotas-iva", tok)
alicuota = next((a for a in alicuotas if float(a["porcentaje"]) == 21.0), None)
if alicuota is None:
    raise SystemExit("no hay alícuota del 21%")

codigo, arbol = pedir("GET", "/api/informes/centros-cuentas", tok)
LUZ = next(c["id"] for c in arbol["centros"][0]["cuentas"] if c["codigo"] == "6.1.03")
PUB = next(c["id"] for c in arbol["centros"][1]["cuentas"] if c["codigo"] == "6.2.01")

compras = []
asientos = []
nueva_compra = []


def crear_compra(cuenta_gasto_id, numero, tipo="factura_a", percepcion=0.0):
    codigo, c = pedir(
        "POST", "/api/compras", tok,
        {
            "proveedor_id": prov["id"],
            "fecha": "2026-09-20",
            "tipo_comprobante": tipo,
            "punto_venta": "0001",
            "numero": numero,
            "concepto": MARCA,
            "neto": 100000.00,
            "alicuota_iva_id": alicuota["id"],
            "percepcion_iva": percepcion,
            "cuenta_gasto_id": cuenta_gasto_id,
        },
    )
    if codigo == 201:
        compras.append(c["id"])
        nueva_compra.append(c)
    return codigo, c


try:
    # --- 1. la cuenta de gasto se valida ------------------------------
    codigo, plan = pedir("GET", "/api/plan-cuentas?q=6.1", tok)
    agrupador = next(c["id_cuenta"] for c in plan if c["codigo"] == "6.1")

    codigo, err = crear_compra(agrupador, "99001")
    chequear("Una cuenta agrupadora (6.1) se rechaza", codigo == 409, str(codigo))

    codigo, plan = pedir("GET", "/api/plan-cuentas?q=1.1.01.01", tok)
    fuera = next(c["id_cuenta"] for c in plan if c["codigo"] == "1.1.01.01")
    codigo, err = crear_compra(fuera, "99002")
    chequear(
        "Una cuenta que NO está bajo 6 GASTOS se rechaza", codigo == 409, str(codigo)
    )
    if isinstance(err, dict) and "detalle" in err:
        chequear(
            "El error dice por qué (menciona el informe por centro)",
            "informe por centro" in err["detalle"],
            err["detalle"][:120],
        )

    codigo, err = crear_compra(999999, "99003")
    chequear("Una cuenta inexistente se rechaza", codigo == 409, str(codigo))

    # --- 2. el preview del asiento ------------------------------------
    # neto 100.000 + IVA 21.000 + percepción 3.000 = 124.000
    cuerpo = {
        "proveedor_id": prov["id"],
        "proveedor_nombre": prov.get("nombre_completo", ""),
        "fecha": "2026-09-20",
        "tipo_comprobante": "factura_a",
        "punto_venta": "0001",
        "numero": "99010",
        "concepto": MARCA,
        "neto": 100000.00,
        "iva": 21000.00,
        "percepcion_iva": 3000.00,
        "total": 124000.00,
        "cuenta_gasto_id": LUZ,
    }
    codigo, pv = pedir("POST", "/api/compras/preview-asiento", tok, cuerpo)
    chequear("El preview del asiento responde 200", codigo == 200, str(codigo))

    if codigo == 200:
        chequear("El preview balancea", pv["balanceado"] is True, str(pv["diferencia"]))
        chequear(
            "El preview no guarda nada (no trae id de asiento)",
            "asiento_id" not in pv,
            str(list(pv.keys())),
        )
        chequear("El preview trae 4 líneas", len(pv["lineas"]) == 4, str(len(pv["lineas"])))

        gasto = linea_por_codigo(pv["lineas"], "6.1.03")
        iva = linea_por_codigo(pv["lineas"], "1.1.05.04")
        perc = linea_por_codigo(pv["lineas"], "1.1.05.06")
        provl = linea_por_codigo(pv["lineas"], "2.1.01.01")

        chequear("El gasto va al DEBE por el neto",
                 gasto and suma(gasto, "debe") == 100000.0 and suma(gasto, "haber") == 0,
                 str(gasto))
        chequear("El IVA crédito fiscal va al DEBE por el IVA entero",
                 iva and suma(iva, "debe") == 21000.0, str(iva))
        chequear("Las percepciones a favor van al DEBE",
                 perc and suma(perc, "debe") == 3000.0, str(perc))
        chequear("Proveedores va al HABER por el total",
                 provl and suma(provl, "haber") == 124000.0, str(provl))
        chequear("El IVA crédito fiscal NO lleva la percepción restada",
                 iva and suma(iva, "debe") == 21000.0,
                 "el IVA tiene que ser 21.000, no 18.000")
        chequear("El auxiliar del proveedor es PROVEEDOR",
                 provl and provl.get("tipo_auxiliar") == "PROVEEDOR", str(provl))

    # --- 3. la NOTA DE CRÉDITO es el asiento al revés ------------------
    cuerpo_nc = dict(cuerpo, tipo_comprobante="nota_credito_a", numero="99011")
    codigo, nc = pedir("POST", "/api/compras/preview-asiento", tok, cuerpo_nc)
    chequear("El preview de la nota de crédito responde 200", codigo == 200, str(codigo))
    if codigo == 200:
        g = linea_por_codigo(nc["lineas"], "6.1.03")
        iv = linea_por_codigo(nc["lineas"], "1.1.05.04")
        pv2 = linea_por_codigo(nc["lineas"], "2.1.01.01")
        chequear("En la nota de crédito el gasto va al HABER",
                 g and suma(g, "haber") == 100000.0 and suma(g, "debe") == 0, str(g))
        chequear("En la nota de crédito el IVA va al HABER",
                 iv and suma(iv, "haber") == 21000.0, str(iv))
        chequear("En la nota de crédito Proveedores va al DEBE",
                 pv2 and suma(pv2, "debe") == 124000.0, str(pv2))
        chequear("La nota de crédito también balancea", nc["balanceado"] is True)

    # --- 4. la compra guardada NO mueve la cuenta ----------------------
    codigo, inf_antes = pedir("GET", "/api/informes/centros-costos", tok)
    total_antes = next(
        c["total"] for c in inf_antes["centros"] if c["codigo"] == "6.1"
    )

    codigo, compra = crear_compra(LUZ, "99020", percepcion=3000.0)
    chequear("La compra se guarda", codigo == 201, str(codigo))
    if codigo != 201:
        raise SystemExit(f"no se pudo crear la compra: {compra}")
    cid = compra["id"]

    chequear("La compra trae su cuenta de gasto",
             compra.get("cuenta_gasto", {}).get("codigo") == "6.1.03",
             str(compra.get("cuenta_gasto")))
    chequear("La compra trae su centro (derivado de la cuenta)",
             compra.get("centro_nombre") == "Gastos de administración",
             str(compra.get("centro_nombre")))
    chequear("La compra guardada NO tiene asiento", compra.get("id_asiento") is None)

    codigo, inf_despues = pedir("GET", "/api/informes/centros-costos", tok)
    total_despues = next(
        c["total"] for c in inf_despues["centros"] if c["codigo"] == "6.1"
    )
    chequear(
        "Guardar la compra NO movió el informe por centro",
        total_despues == total_antes,
        f"{total_antes} → {total_despues}",
    )

    # --- 5. asentar sí mueve ------------------------------------------
    codigo, r = pedir("POST", f"/api/compras/{cid}/asiento", tok)
    chequear("El asiento se genera", codigo == 200 and r.get("generado"), str(codigo))
    if codigo == 200 and r.get("generado"):
        asientos.append(r["asiento_id"])
        chequear("El asiento lleva comprobante propio",
                 bool(r.get("numero_completo")), str(r.get("numero_completo")))
        chequear("El comprobante de la compra es FP (no FV)",
                 r.get("numero_completo", "").startswith("FP-"),
                 str(r.get("numero_completo")))

    codigo, inf_ya = pedir("GET", "/api/informes/centros-costos", tok)
    admin = next(c for c in inf_ya["centros"] if c["codigo"] == "6.1")
    luz = next(k for k in admin["cuentas"] if k["codigo"] == "6.1.03")
    chequear(
        "Asentar la compra mueve el informe por centro",
        admin["total"] - total_antes == 100000.0,
        f"{total_antes} → {admin['total']}",
    )

    codigo, mayor = pedir(
        "GET", f"/api/mayores/{LUZ}?desde=2000-01-01&hasta=2100-01-01", tok
    )
    chequear(
        "El mayor de la cuenta de gasto tiene el mismo número",
        abs(float(mayor["saldo_final"]) - luz["total"]) < 0.005,
        f"mayor {mayor['saldo_final']} vs informe {luz['total']}",
    )

    codigo, compra2 = pedir("GET", f"/api/compras/{cid}", tok)
    chequear("La compra ya muestra su asiento",
             compra2.get("numero_comprobante_asiento", "").startswith("FP-"),
             str(compra2.get("numero_comprobante_asiento")))

    # --- 6. no se asienta dos veces ------------------------------------
    codigo, r2 = pedir("POST", f"/api/compras/{cid}/asiento", tok)
    chequear("No se asienta dos veces", r2.get("generado") is False, str(r2))

    # --- 7. con asiento no se borra ------------------------------------
    codigo, err = pedir("DELETE", f"/api/compras/{cid}", tok)
    chequear("Una compra con asiento no se borra (409)", codigo == 409, str(codigo))

    # --- 8. el filtro "sin asentar" ------------------------------------
    codigo, sin = pedir("GET", "/api/compras?sin_asiento=true", tok)
    chequear("El filtro sin_asiento responde 200", codigo == 200, str(codigo))
    chequear(
        "La compra asentada NO sale del filtro sin_asiento",
        all(c["id"] != cid for c in sin or []),
        str([c["id"] for c in sin or []]),
    )

    # --- 9. anular el asiento saca el gasto del informe ----------------
    codigo, _ = pedir("POST", f"/api/compras/{cid}/asiento/anular", tok)
    chequear("El asiento se anula", codigo == 200, str(codigo))
    codigo, inf_anulada = pedir("GET", "/api/informes/centros-costos", tok)
    admin = next(c for c in inf_anulada["centros"] if c["codigo"] == "6.1")
    chequear(
        "Anular el asiento saca el gasto del informe",
        admin["total"] == total_antes,
        f"{total_antes} → {admin['total']}",
    )
    codigo, compra3 = pedir("GET", f"/api/compras/{cid}", tok)
    chequear("La compra sigue existiendo (solo se anuló el asiento)",
             compra3["estado"] == "pendiente", str(compra3["estado"]))

    # --- 10. el filtro por módulo COMPRA ------------------------------
    codigo, mod = pedir(
        "GET",
        "/api/asientos?desde=2000-01-01&hasta=2100-01-01&origen=COMPRA", tok,
    )
    chequear("El módulo COMPRA existe", codigo == 200, str(codigo))
    codigo, err = pedir(
        "GET", "/api/asientos?desde=2000-01-01&hasta=2100-01-01&origen=COMPRA_X", tok
    )
    chequear("Un módulo inventado se rechaza (400)", codigo == 400, str(codigo))

finally:
    limpiar(tok, compras, asientos)

# --- la base queda como estaba ----------------------------------------
codigo, c = pedir("GET", "/api/compras", tok)
chequear("No quedó ninguna compra de prueba", len(c or []) == 0, str(len(c or [])))

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
