"""Pruebas: código postal + localidad automática, teléfono y borrado solo admin."""

import json
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8010"
resultado = []


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
        with urllib.request.urlopen(req, timeout=10) as resp:
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


def login(usuario, password):
    codigo, datos = pedir(
        "POST", "/api/auth/login", cuerpo={"usuario": usuario, "password": password}
    )
    return datos.get("access_token") if codigo == 200 else None


admin = login("admin", "admin123")
operador = login("operador", "operador123")
chequear("Login admin", admin is not None)
chequear("Login operador", operador is not None)

# ------------------------------------------------------------- localidades
codigo, lista = pedir("GET", "/api/localidades?codigo_postal=5854", admin)
chequear("CP 5854 -> 200", codigo == 200)
chequear("CP 5854 devuelve 1 localidad", len(lista) == 1, f"{len(lista)}")
chequear(
    "CP 5854 = Almafuerte",
    lista and lista[0]["nombre"] == "Almafuerte",
    str(lista),
)
chequear(
    "CP 5854 provincia = Córdoba",
    lista and lista[0]["provincia"] == "Córdoba",
    str(lista),
)

codigo, lista = pedir("GET", "/api/localidades?codigo_postal=5194", admin)
chequear(
    "CP 5194 = Villa General Belgrano",
    codigo == 200 and lista and lista[0]["nombre"] == "Villa General Belgrano",
    str(lista),
)

codigo, lista = pedir("GET", "/api/localidades?codigo_postal=5111", admin)
chequear("CP 5111 = Río Ceballos", lista and lista[0]["nombre"] == "Río Ceballos", str(lista))

codigo, lista = pedir("GET", "/api/localidades?codigo_postal=6120", admin)
chequear("CP 6120 = Laboulaye", lista and lista[0]["nombre"] == "Laboulaye", str(lista))

codigo, lista = pedir("GET", "/api/localidades?codigo_postal=9999", admin)
chequear("CP inexistente -> lista vacía", codigo == 200 and lista == [], str(lista))

codigo, lista = pedir("GET", "/api/localidades?codigo_postal=58", admin)
chequear("CP de 2 dígitos -> lista vacía", codigo == 200 and lista == [], str(lista))

codigo, lista = pedir("GET", "/api/localidades?codigo_postal=5854", None)
chequear("Sin token -> 401", codigo == 401, str(codigo))

codigo, total = pedir("GET", "/api/localidades?codigo_postal=5000", admin)
codigo, listado = pedir("GET", "/api/localidades?codigo_postal=2400", admin)
chequear("81 localidades cargadas (muestra de prueba)", len(listado) == 1, str(listado))

# ------------------------------------------------- cliente con CP y teléfono
# Limpieza previa: si una corrida anterior quedó a medias, el DNI está ocupado
# y el alta da 409 y el test se cae.
_, _previos = pedir("GET", "/api/clientes?q=30111222", admin)
for _c in (_previos or []):
    pedir("DELETE", f"/api/clientes/{_c['id']}", admin)

base = {
    "tipo_persona": "fisica",
    "nombre": "Prueba",
    "apellido": "Cp Tel",
    "dni": "30111222",
    "email": "cptel@ejemplo.com",
    "cod_area": "351",
    "telefono": "1234567",
    "domicilio": "Calle Falsa 123",
    "localidad": "",
    "codigo_postal": "5854",
    "provincia": "",
    "actividad_economica": "comercio",
    "tipo_actividad": "monotributista",
    "condicion_iva": "monotributista",
    "observaciones": "",
    "servicios": [1],
}

codigo, creado = pedir("POST", "/api/clientes", admin, base)
chequear("Alta con CP y teléfono -> 201/200", codigo in (200, 201), str(codigo))
chequear("Guarda cod_area", creado and creado.get("cod_area") == "351", str(creado and creado.get("cod_area")))
chequear("Guarda telefono", creado and creado.get("telefono") == "1234567", str(creado and creado.get("telefono")))
chequear("Guarda codigo_postal", creado and creado.get("codigo_postal") == "5854", str(creado and creado.get("codigo_postal")))
chequear(
    "El backend no inventa la localidad (queda en el cliente)",
    creado and creado.get("localidad") in (None, ""),
    str(creado and creado.get("localidad")),
)

# el frontend habría completado localidad y provincia con el dato del CP
if creado:
    id_cliente = creado["id"]
    con_localidad = dict(base, localidad="Almafuerte", provincia="Córdoba")
    codigo, editado = pedir("PUT", f"/api/clientes/{id_cliente}", admin, con_localidad)
    chequear("PUT con localidad autocompletada -> 200", codigo == 200, str(codigo))
    chequear(
        "Localidad Almafuerte guardada",
        editado and editado.get("localidad") == "Almafuerte",
        str(editado and editado.get("localidad")),
    )

    # el operador puede modificar (los clientes se editan siempre)
    codigo, _ = pedir("PUT", f"/api/clientes/{id_cliente}", operador, con_localidad)
    chequear("Operador puede editar clientes -> 200", codigo == 200, str(codigo))

    # ... pero no puede eliminar: solo el admin
    codigo, datos = pedir("DELETE", f"/api/clientes/{id_cliente}", operador)
    chequear("Operador NO puede eliminar -> 403", codigo == 403, f"{codigo} {datos}")

    codigo, datos = pedir("DELETE", f"/api/clientes/{id_cliente}", admin)
    chequear("Admin sí puede eliminar -> 200/204", codigo in (200, 204), f"{codigo} {datos}")

# ----------------------------------------------------------- validaciones
malos = [
    ("codigo_postal", "585", "código postal"),
    ("codigo_postal", "abcde", "código postal"),
    ("cod_area", "1", "área"),
    ("telefono", "12ab", "teléfono"),
]
for campo, valor, texto_esperado in malos:
    # Un DNI distinto por caso: si el backend aceptara el dato, el cliente
    # quedaría dado de alta y las pruebas siguientes chocarían con el 409.
    cuerpo = dict(base, **{campo: valor}, dni=f"3088{int(valor.isdigit())}{len(valor)}")
    codigo, datos = pedir("POST", "/api/clientes", admin, cuerpo)
    detalle = str(datos)
    chequear(
        f"{campo}={valor} rechazado (422)",
        codigo == 422 and texto_esperado in detalle.lower(),
        f"{codigo} {detalle}",
    )
    if codigo in (200, 201) and isinstance(datos, dict) and datos.get("id"):
        # Si lo.bindingMSLogic aceptara (no debería), se borra para no dejar basura.
        pedir("DELETE", f"/api/clientes/{datos['id']}", admin)

# campos opcionales: sin teléfono se puede dar de alta
sin_tel = dict(base, cod_area=None, telefono=None, codigo_postal=None, dni="30999888")
codigo, creado2 = pedir("POST", "/api/clientes", admin, sin_tel)
chequear("Alta sin teléfono ni CP -> 201/200", codigo in (200, 201), str(codigo))
if creado2:
    pedir("DELETE", f"/api/clientes/{creado2['id']}", admin)

# ------------------------------------------------------------------ reporte
fallidos = [r for r in resultado if not r[1]]
for nombre, ok, detalle in resultado:
    print(f"  {'OK  ' if ok else 'FALLA'} {nombre}" + (f"  -> {detalle}" if not ok else ""))
print(f"\n{len(resultado) - len(fallidos)}/{len(resultado)} pruebas correctas.")
raise SystemExit(1 if fallidos else 0)
