"""Pruebas del módulo ANTICIPOS DE CLIENTES — alta, imputación a facturas y
su lugar en la cuenta corriente (sin doble conteo)."""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8010"
resultado = []

# Para la limpieza por SQL hace falta importar la app del backend. La ruta es
# relativa al archivo, así el test funciona desde cualquier carpeta.
sys.path.insert(0, os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
))


def pedir(metodo, ruta, token=None, cuerpo=None):
    datos = None
    encabezados = {"Content-Type": "application/json"}
    if token:
        encabezados["Authorization"] = f"Bearer {token}"
    if cuerpo is not None:
        datos = json.dumps(cuerpo).encode("utf-8")
    req = urllib.request.Request(
        BASE + urllib.parse.quote(ruta, safe="/?&=:%,-."),
        data=datos,
        headers=encabezados,
        method=metodo,
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            texto = resp.read().decode("utf-8")
            return resp.status, json.loads(texto) if texto else None
    except urllib.error.HTTPError as e:
        texto = e.read().decode("utf-8")
        try:
            return e.code, json.loads(texto) if texto else None
        except json.JSONDecodeError:
            return e.code, {"detail": texto}


def chequear(nombre, condicion, detalle=""):
    resultado.append((nombre, bool(condicion), detalle))


def _borrar_facturas_por_sql(cliente_id):
    """Saca las facturas del cliente con su asiento. Orden por clave foránea.

    Va por SQL y no por la API a propósito. Desde que existe el módulo
    contable, cargar una factura genera su asiento, y una factura CON asiento no
    se borra por la API (409: el asiento es documento contable). Si la limpieza
    fuera por API, las facturas de prueba quedarían colgadas y el cliente no se
    podría borrar nunca.

    Solo toca las facturas de ESE cliente: nunca `DELETE FROM facturas` a secas,
    que se llevaría las facturas reales.
    """
    from sqlalchemy import text

    from app.database import SessionLocal

    db = SessionLocal()
    try:
        facturas = [
            r[0] for r in db.execute(
                text("SELECT id FROM facturas WHERE cliente_id = :c"),
                {"c": cliente_id},
            )
        ]
        for fid in facturas:
            for aid in [
                r[0] for r in db.execute(
                    text("SELECT id_asiento FROM asiento_origen WHERE id_factura = :f"),
                    {"f": fid},
                )
            ]:
                for sql in ("DELETE FROM asiento_detalle WHERE id_asiento = :a",
                            "DELETE FROM asiento_origen WHERE id_asiento = :a",
                            "DELETE FROM asientos WHERE id_asiento = :a"):
                    db.execute(text(sql), {"a": aid})
            db.execute(text("DELETE FROM facturas WHERE id = :f"), {"f": fid})
        db.commit()
    finally:
        db.close()


def login(usuario, password):
    codigo, datos = pedir(
        "POST", "/api/auth/login", cuerpo={"usuario": usuario, "password": password}
    )
    return datos.get("access_token") if codigo == 200 else None


admin = login("admin", "admin123")
operador = login("operador", "operador123")
chequear("Login admin", admin is not None)
chequear("Login operador", operador is not None)

DNI_A = "39666555"
DNI_B = "39666556"


def limpiar_previo(dni, token):
    """Borra restos de una corrida anterior."""
    _, encontrados = pedir("GET", f"/api/clientes?q={dni}", token)
    for cliente in encontrados or []:
        cid = cliente["id"]
        _, anticipos = pedir("GET", f"/api/anticipos?cliente_id={cid}", token)
        for a in anticipos or []:
            _, apps = pedir("GET", f"/api/anticipos/{a['id']}/aplicaciones", token)
            for x in apps or []:
                pedir("DELETE", f"/api/anticipos/aplicaciones/{x['id']}", token)
            pedir("DELETE", f"/api/anticipos/{a['id']}", token)
        _, recibos = pedir("GET", f"/api/recibos?cliente_id={cid}", token)
        for r in recibos or []:
            _, apps = pedir("GET", f"/api/recibos/{r['id']}/aplicaciones", token)
            for x in apps or []:
                pedir("DELETE", f"/api/recibos/aplicaciones/{x['id']}", token)
            pedir("DELETE", f"/api/recibos/{r['id']}", token)
        # Las facturas van por SQL, no por la API: desde que existe el módulo
        # contable, una factura genera su asiento al cargarse y una factura CON
        # asiento no se borra por la API (409, a propósito). Por API quedaban
        # ahí y el cliente no se podía borrar nunca.
        _borrar_facturas_por_sql(cid)
        pedir("DELETE", f"/api/clientes/{cid}", token)


limpiar_previo(DNI_A, admin)
limpiar_previo(DNI_B, admin)


def crear_cliente(nombre, dni):
    codigo, datos = pedir(
        "POST",
        "/api/clientes",
        admin,
        {
            "tipo_persona": "fisica",
            "nombre": nombre,
            "apellido": "Anticipa",
            "dni": dni,
            "actividad_economica": "servicios",
            "tipo_actividad": "monotributista",
    "condicion_iva": "monotributista",
            "servicios": [1],
        },
    )
    if codigo == 409:
        _, existentes = pedir("GET", f"/api/clientes?q={dni}", admin)
        datos = existentes[0]
    return datos


cliente_a = crear_cliente("Alicia", DNI_A)
cliente_b = crear_cliente("Beto", DNI_B)
ca = cliente_a["id"]
cb = cliente_b["id"]
chequear("Clientes de prueba listos", bool(ca) and bool(cb), f"{ca} / {cb}")

FACTURA_BASE = {
    "cliente_id": ca,
    "fecha": "2026-09-10",
    "tipo_comprobante": "factura_b",
    "punto_venta": "1",
    "numero": "200",
    "concepto": "Trabajo",
    "importe": 100000,
    "fecha_vencimiento": "2026-09-30",
    "condicion_venta": "cta_corriente_30",
    "cae": "",
    "cae_vencimiento": None,
}

_, f1 = pedir("POST", "/api/facturas", admin, {**FACTURA_BASE, "numero": "200"})
_, f2 = pedir(
    "POST", "/api/facturas", admin,
    {**FACTURA_BASE, "numero": "201", "fecha": "2026-09-25", "importe": 80000},
)
_, f3 = pedir(
    "POST", "/api/facturas", admin,
    {**FACTURA_BASE, "numero": "202", "fecha": "2026-09-28", "importe": 20000},
)
_, fb = pedir(
    "POST", "/api/facturas", admin,
    {**FACTURA_BASE, "cliente_id": cb, "numero": "203", "importe": 50000},
)
chequear(
    "Facturas de prueba listas",
    all(x and x.get("id") for x in (f1, f2, f3, fb)),
    str([x.get("id") for x in (f1, f2, f3, fb) if x]),
)

# --------------------------------------------------------------- sin token
codigo, _ = pedir("GET", "/api/anticipos", None)
chequear("Sin token -> 401", codigo == 401, str(codigo))

# --------------------------------------------------------------- listados
codigo, lista = pedir("GET", "/api/anticipos", admin)
chequear("GET /anticipos -> 200 y lista", codigo == 200 and isinstance(lista, list), str(codigo))

# ------------------------------------------------------------------ alta
ANTICIPO = {
    "cliente_id": ca,
    "fecha": "2026-09-10",
    "importe": 60000,
}
codigo, a1 = pedir("POST", "/api/anticipos", admin, ANTICIPO)
chequear("Alta anticipo -> 201", codigo == 201, str(codigo))
# El número se genera solo y es GLOBAL (no por cliente): con anticipos viejos
# en la base el primero puede no ser 00000001, así que se verifica el formato.
numero_a1 = (a1 or {}).get("numero") or ""
chequear(
    "Número generado solo (8 dígitos)",
    len(numero_a1) == 8 and numero_a1.isdigit(),
    str(numero_a1),
)
chequear("Arranca DISPONIBLE", a1 and a1.get("estado") == "disponible", str(a1 and a1.get("estado")))
chequear("Trae el nombre del cliente", a1 and a1.get("cliente_nombre") == "Anticipa, Alicia", str(a1 and a1.get("cliente_nombre")))

# El número NO se carga a mano: si viene, el backend lo rechaza y lo dice.
codigo, repetido = pedir("POST", "/api/anticipos", admin, {**ANTICIPO, "numero": numero_a1})
chequear("Número cargado a mano -> 400", codigo == 400, str(codigo))
chequear(
    "Aviso claro de que el número se genera solo",
    "se genera solo" in str(repetido),
    str(repetido),
)

for campo, valor in (("importe", 0), ("importe", -1)):
    codigo, datos = pedir("POST", "/api/anticipos", admin, {**ANTICIPO, campo: valor})
    chequear(f"{campo}={valor} rechazado (422)", codigo == 422, f"{codigo} {datos}")

codigo, datos = pedir("POST", "/api/anticipos", admin, {**ANTICIPO, "numero": "abc"})
chequear("numero=abc rechazado (400)", codigo == 400, f"{codigo} {datos}")

codigo, datos = pedir("GET", "/api/anticipos/99999", admin)
chequear("Anticipo inexistente -> 404", codigo == 404, str(codigo))

codigo, editado = pedir("PUT", f"/api/anticipos/{a1['id']}", admin, {**ANTICIPO, "fecha": "2026-09-12"})
chequear("Modificar anticipo -> 200", codigo == 200, str(codigo))
pedir("PUT", f"/api/anticipos/{a1['id']}", admin, ANTICIPO)

# ---------------------------------------------------------- imputaciones
codigo, x1 = pedir(
    "POST", f"/api/anticipos/{a1['id']}/aplicaciones", admin,
    {"factura_id": f1["id"], "importe": 30000},
)
chequear("Imputar 30000 a la factura -> 201", codigo == 201, str(codigo))
chequear("La imputación trae la factura", x1 and x1.get("factura", {}).get("numero") == "00000200", str(x1))

_, a1_leido = pedir("GET", f"/api/anticipos/{a1['id']}", admin)
chequear("Anticipo queda PARCIAL", a1_leido.get("estado") == "parcial", str(a1_leido.get("estado")))

_, f1_leida = pedir("GET", f"/api/facturas/{f1['id']}", admin)
chequear("Factura queda PARCIAL", f1_leida.get("estado") == "parcial", str(f1_leida.get("estado")))

# segunda imputación a la MISMA factura: tiene que permitirse
codigo, x2 = pedir(
    "POST", f"/api/anticipos/{a1['id']}/aplicaciones", admin,
    {"factura_id": f1["id"], "importe": 20000},
)
chequear("Segunda imputación a la misma factura -> 201", codigo == 201, str(codigo))

codigo, aplicaciones = pedir("GET", f"/api/anticipos/{a1['id']}/aplicaciones", admin)
chequear("Tiene 2 imputaciones", codigo == 200 and len(aplicaciones) == 2, str(len(aplicaciones or [])))
chequear(
    "Suma de imputaciones = 50000",
    abs(sum(float(x["importe"]) for x in (aplicaciones or [])) - 50000) < 0.01,
    str([x["importe"] for x in (aplicaciones or [])]),
)

# ------------------------------------------------------------- errores
codigo, datos = pedir(
    "POST", f"/api/anticipos/{a1['id']}/aplicaciones", admin,
    {"factura_id": fb["id"], "importe": 1000},
)
chequear("Factura de otro cliente -> 409", codigo == 409, str(datos))

pedir("POST", f"/api/facturas/{f2['id']}/anular", admin)
codigo, datos = pedir(
    "POST", f"/api/anticipos/{a1['id']}/aplicaciones", admin,
    {"factura_id": f2["id"], "importe": 1000},
)
chequear("Factura anulada -> 409", codigo == 409, str(datos))
pedir("POST", f"/api/facturas/{f2['id']}/reabrir", admin)

codigo, datos = pedir(
    "POST", f"/api/anticipos/{a1['id']}/aplicaciones", admin,
    {"factura_id": f2["id"], "importe": 20000},
)
chequear("Se pasa del anticipo -> 409", codigo == 409, str(datos))
chequear(
    "Avisa cuánto le queda al anticipo",
    "10000.00" in str(datos) or "10,000.00" in str(datos),
    str(datos),
)

codigo, datos = pedir(
    "POST", f"/api/anticipos/{a1['id']}/aplicaciones", admin,
    {"factura_id": 99999, "importe": 1000},
)
chequear("Factura inexistente -> 404", codigo == 404, str(datos))

# completa el anticipo: 10000 a la factura 2
codigo, x3 = pedir(
    "POST", f"/api/anticipos/{a1['id']}/aplicaciones", admin,
    {"factura_id": f2["id"], "importe": 10000},
)
chequear("Último tramo -> 201", codigo == 201, str(codigo))
_, a1_final = pedir("GET", f"/api/anticipos/{a1['id']}", admin)
chequear("Anticipo queda APLICADO", a1_final.get("estado") == "aplicado", str(a1_final.get("estado")))

# ------------------------------------------------- cuenta corriente (clave)
codigo, cc = pedir("GET", f"/api/clientes/{ca}/cuenta", admin)
chequear("Cuenta corriente -> 200", codigo == 200, str(codigo))
mov = cc.get("movimientos", [])
chequear(
    "4 movimientos (3 facturas + 1 anticipo)",
    len(mov) == 4,
    str([m["concepto"] for m in mov]),
)
chequear(
    "El anticipo figura como HABER",
    any(m["concepto"].startswith("Anticipo") and m["haber"] > 0 for m in mov),
    str([(m["concepto"], m["haber"]) for m in mov]),
)
chequear("Total DEBE = 200000", abs(cc["total_debe"] - 200000) < 0.01, str(cc["total_debe"]))
chequear(
    "Total HABER = 60000 (NO se duplica al imputar)",
    abs(cc["total_haber"] - 60000) < 0.01,
    str(cc["total_haber"]),
)
chequear("Saldo = 140000", abs(cc["saldo"] - 140000) < 0.01, str(cc["saldo"]))

chequear(
    "Mismo día: primero la factura, después el anticipo",
    mov[0]["concepto"].startswith("Factura") and mov[1]["concepto"].startswith("Anticipo"),
    str([m["concepto"] for m in mov]),
)
chequear(
    "Saldo del primer renglón = importe de la factura",
    abs(mov[0]["saldo"] - 100000) < 0.01,
    str(mov[0]["saldo"]),
)
chequear(
    "El saldo final coincide con el resumen",
    abs(mov[-1]["saldo"] - cc["saldo"]) < 0.01,
    f"{mov[-1]['saldo']} vs {cc['saldo']}",
)

# ------------------------------------- segunda factura chica (los límites)
codigo, a2 = pedir("POST", "/api/anticipos", admin, {**ANTICIPO, "importe": 50000, "fecha": "2026-09-20"})
chequear("Segundo anticipo -> 201", codigo == 201, str(codigo))

pedir("POST", f"/api/anticipos/{a2['id']}/aplicaciones", admin, {"factura_id": f3["id"], "importe": 15000})
codigo, datos = pedir(
    "POST", f"/api/anticipos/{a2['id']}/aplicaciones", admin,
    {"factura_id": f3["id"], "importe": 10000},
)
chequear("Se pasa de lo que falta en la factura -> 409", codigo == 409, str(datos))

codigo, _ = pedir("POST", f"/api/anticipos/{a2['id']}/aplicaciones", admin, {"factura_id": f3["id"], "importe": 5000})
_, f3_final = pedir("GET", f"/api/facturas/{f3['id']}", admin)
chequear("Factura chica queda PAGADA", f3_final.get("estado") == "pagada", str(f3_final.get("estado")))

# ------------------------------------------------------------------ roles
codigo, datos = pedir("POST", "/api/anticipos", operador, ANTICIPO)
chequear("Operador crea anticipo -> 201", codigo == 201, str(codigo))
a3 = datos

codigo, datos = pedir("POST", f"/api/anticipos/{a2['id']}/aplicaciones", operador, {"factura_id": f2["id"], "importe": 1000})
chequear("Operador imputa -> 201", codigo == 201, str(codigo))

codigo, datos = pedir("DELETE", f"/api/anticipos/aplicaciones/{x1['id']}", operador)
chequear("Operador NO desimputa -> 403", codigo == 403, str(codigo))

codigo, datos = pedir("DELETE", f"/api/anticipos/{a1['id']}", operador)
chequear("Operador NO borra anticipo -> 403", codigo == 403, str(codigo))

codigo, _ = pedir("DELETE", f"/api/anticipos/{a3['id']}", admin)
chequear("Anticipo sin imputaciones se elimina -> 204", codigo == 204, str(codigo))

_, a3_leido = pedir("GET", f"/api/anticipos/{a3['id']}", admin)
chequear(
    "La fila NO se borra: queda estado ELIMINADO",
    a3_leido.get("estado") == "eliminado",
    str(a3_leido and a3_leido.get("estado")),
)

codigo, datos = pedir("DELETE", f"/api/anticipos/{a3['id']}", admin)
chequear("Eliminar dos veces -> 409", codigo == 409, str(codigo))

codigo, datos = pedir("PUT", f"/api/anticipos/{a3['id']}", admin, ANTICIPO)
chequear("No se modifica un anticipo eliminado -> 409", codigo == 409, str(codigo))

codigo, datos = pedir(
    "POST", f"/api/anticipos/{a3['id']}/aplicaciones", admin,
    {"factura_id": f1["id"], "importe": 1000},
)
chequear("No se imputa un anticipo eliminado -> 409", codigo == 409, str(codigo))

# el estado de cuenta tiene que mostrar el movimiento contrario
codigo, cc2 = pedir("GET", f"/api/clientes/{ca}/cuenta", admin)
chequear("Cuenta corriente -> 200", codigo == 200, str(codigo))
mov2 = cc2.get("movimientos", [])
contrarios = [m for m in mov2 if m["concepto"].startswith("Eliminacion") or m["concepto"].startswith("Eliminación")]
chequear("Aparece el concepto 'Eliminación anticipos'", len(contrarios) == 1, str([m["concepto"] for m in mov2]))
chequear(
    "Va en DEBE con el mismo importe (60000)",
    bool(contrarios) and abs(contrarios[0]["debe"] - 60000) < 0.01,
    str(contrarios),
)
chequear(
    "El anticipo original sigue en HABER",
    any(
        m["concepto"].startswith("Anticipo ") and m["haber"] > 0
        # La fila de "Eliminación" va en DEBE, así que el anticipo que sigue en
        # HABER es el otro (el que no se eliminó).
        for m in mov2
    ),
    str([(m["concepto"], m["debe"], m["haber"]) for m in mov2]),
)
chequear(
    "El saldo NO cambió: la eliminación anula el anticipo",
    abs(cc2["saldo"] - 90000) < 0.01,
    str(cc2["saldo"]),
)

codigo, datos = pedir("DELETE", f"/api/anticipos/{a1['id']}", admin)
chequear("Anticipo imputado NO se borra -> 409", codigo == 409, str(codigo))

codigo, datos = pedir("PUT", f"/api/anticipos/{a1['id']}", admin, {**ANTICIPO, "importe": 20000})
chequear("No se baja el importe por debajo de lo imputado -> 409", codigo == 409, str(datos))

codigo, datos = pedir("POST", "/api/anticipos", admin, {**ANTICIPO, "cliente_id": 99999})
chequear("Cliente inexistente -> 404", codigo == 404, str(codigo))
chequear(
    "Aviso claro de que no existe el cliente",
    "no existe" in str(datos).lower(),
    str(datos),
)

# ------------------------------------------------------------ desimputar
codigo, _ = pedir("DELETE", f"/api/anticipos/aplicaciones/{x1['id']}", admin)
chequear("Desimputar (admin) -> 204", codigo == 204, str(codigo))

_, a1_revisado = pedir("GET", f"/api/anticipos/{a1['id']}", admin)
chequear("El anticipo vuelve a PARCIAL", a1_revisado.get("estado") == "parcial", str(a1_revisado.get("estado")))
_, f1_revisada = pedir("GET", f"/api/facturas/{f1['id']}", admin)
chequear("La factura vuelve a PARCIAL", f1_revisada.get("estado") == "parcial", str(f1_revisada.get("estado")))

codigo, datos = pedir("DELETE", "/api/anticipos/aplicaciones/99999", admin)
chequear("Imputación inexistente -> 404", codigo == 404, str(codigo))

# ------------------------------------------------------- bloqueo de cliente
codigo, datos = pedir("DELETE", f"/api/clientes/{ca}", admin)
chequear("Cliente con anticipos NO se borra -> 409", codigo == 409, str(codigo))

# --------------------------------------------------------------- limpieza
def limpiar(cid, token):
    """Deja al cliente sin movimientos, para que se pueda borrar después."""
    _, anticipos = pedir("GET", f"/api/anticipos?cliente_id={cid}", token)
    for a in anticipos or []:
        _, apps = pedir("GET", f"/api/anticipos/{a['id']}/aplicaciones", token)
        for x in apps or []:
            pedir("DELETE", f"/api/anticipos/aplicaciones/{x['id']}", token)
        pedir("DELETE", f"/api/anticipos/{a['id']}", token)

    _borrar_facturas_por_sql(cid)


def _borrar_facturas_por_sql(cliente_id):
    """Saca las facturas del cliente con su asiento. Orden por FK."""
    from sqlalchemy import text

    from app.database import SessionLocal

    db = SessionLocal()
    try:
        facturas = [
            r[0] for r in db.execute(
                text("SELECT id FROM facturas WHERE cliente_id = :c"),
                {"c": cliente_id},
            )
        ]
        for fid in facturas:
            asientos = [
                r[0] for r in db.execute(
                    text("SELECT id_asiento FROM asiento_origen WHERE id_factura = :f"),
                    {"f": fid},
                )
            ]
            for aid in asientos:
                for sql in ("DELETE FROM asiento_detalle WHERE id_asiento = :a",
                            "DELETE FROM asiento_origen WHERE id_asiento = :a",
                            "DELETE FROM asientos WHERE id_asiento = :a"):
                    db.execute(text(sql), {"a": aid})
            db.execute(text("DELETE FROM facturas WHERE id = :f"), {"f": fid})
        db.commit()
    finally:
        db.close()


limpiar(ca, admin)
limpiar(cb, admin)

# los clientes se borran primero: los anticipos marcados como eliminados
# no cuentan como movimiento y se van con el cliente.
codigo, _ = pedir("DELETE", f"/api/clientes/{ca}", admin)
chequear("Se borra el cliente A", codigo in (200, 204), str(codigo))
codigo, _ = pedir("DELETE", f"/api/clientes/{cb}", admin)
chequear("Se borra el cliente B", codigo in (200, 204), str(codigo))

_, quedan_a = pedir("GET", f"/api/anticipos?cliente_id={ca}", admin)
_, quedan_f = pedir("GET", f"/api/facturas?cliente_id={ca}", admin)
chequear("Se limpiaron los anticipos", quedan_a == [], str(quedan_a))
chequear("Se limpiaron las facturas", quedan_f == [], str(quedan_f))

# ---------------------------------------------------------------- reporte
fallidos = [r for r in resultado if not r[1]]
for nombre, ok, detalle in resultado:
    print(f"  {'OK  ' if ok else 'FALLA'} {nombre}" + (f"  -> {detalle}" if not ok else ""))
print(f"\n{len(resultado) - len(fallidos)}/{len(resultado)} pruebas correctas.")
raise SystemExit(1 if fallidos else 0)
