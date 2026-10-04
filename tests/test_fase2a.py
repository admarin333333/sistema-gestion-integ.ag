"""Pruebas de la Fase 2A — Backend de clientes."""

import os
import json
import urllib.error
import urllib.parse
import urllib.request
# La dirección de la API sale de `GC_BASE_URL` para poder correr estas pruebas
# contra la base de PRUEBAS y no contra la del estudio. Si la variable no
# está, usa 8010 como antes: no cambia cómo se corren.

BASE = os.environ.get("GC_BASE_URL", "http://127.0.0.1:8010")
resultado = []


def pedir(metodo, ruta, token=None, cuerpo=None):
    datos = None
    encabezados = {"Content-Type": "application/json"}
    if token:
        encabezados["Authorization"] = f"Bearer {token}"
    if cuerpo is not None:
        datos = json.dumps(cuerpo).encode("utf-8")
    req = urllib.request.Request(
        BASE + urllib.parse.quote(ruta, safe="/?&=:%,-."), data=datos,
        headers=encabezados, method=metodo,
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
    codigo, datos = pedir("POST", "/api/auth/login", cuerpo={"usuario": usuario, "password": password})
    return datos.get("access_token") if codigo == 200 else None


admin = login("admin", "admin123")
operador = login("operador", "operador123")
chequear("Login admin", admin is not None)
chequear("Login operador", operador is not None)

# La base puede tener clientes reales: los guardo para no tocarlos.
_, base_inicial = pedir("GET", "/api/clientes", admin)
ids_iniciales = {c["id"] for c in (base_inicial or [])}
ids_de = lambda lista: [c["id"] for c in (lista or [])]  # noqa: E731
incluye = lambda lista, *ids: set(ids_de(lista)) >= set(ids)  # noqa: E731

# ---------------------------------------------------------------- servicios
codigo, servicios = pedir("GET", "/api/servicios", admin)
chequear("GET /servicios -> 200", codigo == 200)
chequear("Hay 10 servicios", len(servicios) == 10, f"llegaron {len(servicios)}")

# ---------------------------------------------------------------- alta física
fisica = {
    "tipo_persona": "fisica", "nombre": "Juan", "apellido": "Pérez",
    "cuit": "20-31555666-0", "dni": "31555666", "email": "juan@ejemplo.com",
    "domicilio": "Av. Siempreviva 742", "localidad": "Córdoba", "provincia": "Córdoba",
    "actividad_economica": "profesional", "tipo_actividad": "monotributista",
    "condicion_iva": "monotributista",
    "observaciones": "Cliente desde 2024", "servicios": [1, 2],
}
codigo, cliente = pedir("POST", "/api/clientes", admin, fisica)
chequear("Alta persona física -> 201", codigo == 201, str(codigo))
id_fisica = cliente.get("id") if cliente else None
chequear("Devuelve número de cuenta", isinstance(id_fisica, int))
chequear("CUIT se normaliza a 20-31555666-0", cliente.get("cuit") == "20-31555666-0", cliente.get("cuit"))
chequear("Trae los 2 servicios", len(cliente.get("servicios", [])) == 2)
chequear("nombre_completo = 'Pérez, Juan'", cliente.get("nombre_completo") == "Pérez, Juan", cliente.get("nombre_completo"))

# ---------------------------------------------------------------- duplicados
codigo, datos = pedir("POST", "/api/clientes", admin, {**fisica, "dni": "30000000"})
chequear("CUIT repetido -> 409", codigo == 409, str(codigo))
chequear("Aviso claro de CUIT", "CUIT" in (datos or {}).get("detail", ""), (datos or {}).get("detail"))

codigo, datos = pedir("POST", "/api/clientes", admin, {**fisica, "cuit": "27-30000000-8"})
chequear("DNI repetido -> 409", codigo == 409, str(codigo))
chequear("Aviso claro de DNI", "DNI" in (datos or {}).get("detail", ""), (datos or {}).get("detail"))

# ---------------------------------------------------------------- validaciones
codigo, datos = pedir("POST", "/api/clientes", admin, {**fisica, "apellido": None})
chequear("Física sin apellido -> 422", codigo == 422, str(codigo))

codigo, datos = pedir("POST", "/api/clientes", admin, {**fisica, "dni": None})
chequear("Física sin DNI -> 422", codigo == 422, str(codigo))

codigo, datos = pedir("POST", "/api/clientes", admin, {**fisica, "cuit": "20-123"})
chequear("CUIT con 5 dígitos -> 422", codigo == 422, str(codigo))

codigo, datos = pedir("POST", "/api/clientes", admin, {**fisica, "dni": "12AB"})
chequear("DNI con letras -> 422", codigo == 422, str(codigo))

codigo, datos = pedir("POST", "/api/clientes", admin, {**fisica, "email": "no-es-un-email"})
chequear("Email inválido -> 422", codigo == 422, str(codigo))

codigo, datos = pedir("POST", "/api/clientes", admin, {**fisica, "tipo_persona": "robot"})
chequear("Tipo de persona inválido -> 422", codigo == 422, str(codigo))

codigo, datos = pedir("POST", "/api/clientes", admin,
                     {**fisica, "cuit": "27-30000001-6", "dni": "30000001", "servicios": [999]})
chequear("Servicio inexistente -> 400", codigo == 400, str(codigo))

# ---------------------------------------------------------------- jurídica
juridica = {
    "tipo_persona": "juridica", "nombre": "Distribuidora Norte SRL",
    "cuit": "30-71888999-1", "dni": None, "email": "admin@norte.com",
    "domicilio": "Santa Fe 1234", "localidad": "Córdoba", "provincia": "Córdoba",
    "actividad_economica": "comercio", "tipo_actividad": "responsable_inscripto",
    "condicion_iva": "responsable_inscripto",
    "observaciones": None, "servicios": [4],
}
codigo, empresa = pedir("POST", "/api/clientes", operador, juridica)
chequear("Alta jurídica (como operador) -> 201", codigo == 201, str(codigo))
id_juridica = empresa.get("id") if empresa else None
chequear("Jurídica usa el nombre como razón social", empresa.get("nombre_completo") == "Distribuidora Norte SRL", empresa.get("nombre_completo"))

codigo, datos = pedir("POST", "/api/clientes", admin, {**juridica, "cuit": None})
chequear("Jurídica sin CUIT -> 422", codigo == 422, str(codigo))

codigo, datos = pedir("POST", "/api/clientes", admin, {**juridica, "cuit": "30-70000000-8", "dni": "70000000"})
chequear("Jurídica con DNI -> 422", codigo == 422, str(codigo))

# ---------------------------------------------------------------- búsquedas
codigo, lista = pedir("GET", "/api/clientes?q=Pérez", admin)
chequear("Busca por apellido", codigo == 200 and incluye(lista, id_fisica), f"llegó {len(lista or [])}")

codigo, lista = pedir("GET", "/api/clientes?q=31555666", admin)
chequear("Busca por DNI", codigo == 200 and incluye(lista, id_fisica), f"llegó {len(lista or [])}")

codigo, lista = pedir("GET", "/api/clientes?q=20315556660", admin)
chequear("Busca por CUIT sin guiones", codigo == 200 and incluye(lista, id_fisica), f"llegó {len(lista or [])}")

codigo, lista = pedir("GET", "/api/clientes?q=20-31555666-0", admin)
chequear("Busca por CUIT con guiones", codigo == 200 and incluye(lista, id_fisica), f"llegó {len(lista or [])}")

codigo, lista = pedir("GET", "/api/clientes?q=norte", admin)
chequear("Busca razón social", codigo == 200 and incluye(lista, id_juridica), f"llegó {len(lista or [])}")

esperados = ids_iniciales | {id_fisica, id_juridica}
codigo, lista = pedir("GET", "/api/clientes", admin)
chequear("Listado completo", codigo == 200 and set(ids_de(lista)) >= esperados, f"llegó {len(lista or [])}")

codigo, lista = pedir("GET", "/api/clientes", operador)
chequear("Operador puede ver el listado", codigo == 200 and set(ids_de(lista)) >= esperados)

codigo, lista = pedir("GET", "/api/clientes")
chequear("Sin token -> 401", codigo == 401, str(codigo))

# ---------------------------------------------------------------- ficha
codigo, ficha = pedir("GET", f"/api/clientes/{id_fisica}", admin)
chequear("Ficha -> 200", codigo == 200, str(codigo))
chequear("Ficha trae servicios", len(ficha.get("servicios", [])) == 2)
chequear("Ficha trae sugerencias (vacío)", ficha.get("sugerencias") == [])

codigo, datos = pedir("GET", "/api/clientes/99999", admin)
chequear("Cliente inexistente -> 404", codigo == 404, str(codigo))

# ---------------------------------------------------------------- edición
codigo, editado = pedir("PUT", f"/api/clientes/{id_fisica}", admin, {**fisica, "observaciones": "Pasa a responsabile inscripto", "servicios": [2, 3]})
chequear("Modificar -> 200", codigo == 200, str(codigo))
chequear("Se guardó la observación", editado.get("observaciones") == "Pasa a responsabile inscripto")
chequear("Cambió a 2 servicios distintos", sorted(s["id"] for s in editado.get("servicios", [])) == [2, 3])
chequear("Quedó marcado actualizado", editado.get("actualizado") is not None)

codigo, editado = pedir("PUT", f"/api/clientes/{id_fisica}", operador, {**fisica, "observaciones": "Editado por operador"})
chequear("Operador puede modificar", codigo == 200, str(codigo))

# ---------------------------------------------------------------- sugerencias
sugerencia = {"fecha": "2026-09-30", "descripcion": "Buscar asesor legal para el contrato", "estado": "pendiente"}
codigo, nueva = pedir("POST", f"/api/clientes/{id_fisica}/sugerencias", operador, sugerencia)
# El endpoint de sugerencias devuelve 200 (no 201 como el resto de los altos).
chequear("Alta sugerencia -> 200", codigo == 200, str(codigo))
id_sug = nueva.get("id") if nueva else None

pedir("POST", f"/api/clientes/{id_fisica}/sugerencias", admin,
      {"fecha": "2026-10-01", "descripcion": "Hacer plan de pagos", "estado": "pendiente"})
pedir("POST", f"/api/clientes/{id_fisica}/sugerencias", admin,
      {"fecha": "2026-10-02", "descripcion": "Ponerse al día con las obligaciones impositivas ejecutadas", "estado": "pendiente"})

codigo, lista = pedir("GET", f"/api/clientes/{id_fisica}/sugerencias", admin)
chequear("3 sugerencias cargadas", codigo == 200 and len(lista) == 3, f"llegó {len(lista or [])}")
chequear("Ordenadas por fecha descendente", lista[0]["fecha"] >= lista[-1]["fecha"], f"{lista[0]['fecha']} .. {lista[-1]['fecha']}")

codigo, lista = pedir("GET", f"/api/clientes/{id_juridica}/sugerencias", admin)
chequear("Jurídica sin sugerencias", codigo == 200 and len(lista) == 0)

codigo, dato = pedir("PUT", f"/api/sugerencias/{id_sug}", operador, {**sugerencia, "estado": "atendida"})
chequear("Marcar como atendida -> 200", codigo == 200, str(codigo))
chequear("Estado guardado", dato.get("estado") == "atendida")

codigo, dato = pedir("PUT", f"/api/sugerencias/{id_sug}", admin, {**sugerencia, "estado": "volando"})
chequear("Estado inválido -> 422", codigo == 422, str(codigo))

codigo, dato = pedir("POST", f"/api/clientes/{id_fisica}/sugerencias", admin, {"fecha": "2026-10-01", "descripcion": "  "})
chequear("Descripción vacía -> 422", codigo == 422, str(codigo))

# ---------------------------------------------------------------- borrados
codigo, datos = pedir("DELETE", f"/api/clientes/{id_fisica}", operador)
chequear("Operador NO puede borrar clientes -> 403", codigo == 403, str(codigo))

codigo, datos = pedir("DELETE", f"/api/sugerencias/{id_sug}", operador)
chequear("Operador NO puede borrar sugerencias -> 403", codigo == 403, str(codigo))

codigo, datos = pedir("DELETE", f"/api/clientes/{id_fisica}", admin)
chequear("Admin borra cliente sin movimientos -> 204", codigo == 204, str(codigo))

codigo, datos = pedir("GET", f"/api/clientes/{id_fisica}", admin)
chequear("El cliente ya no existe", codigo == 404, str(codigo))

codigo, base = pedir("GET", "/api/clientes", admin)
chequear(
    "Solo queda la jurídica de prueba (la física ya se borró)",
    codigo == 200 and set(ids_de(base)) == ids_iniciales | {id_juridica},
    f"quedaron {set(ids_de(base)) - ids_iniciales - {id_juridica}}",
)

codigo, datos = pedir("DELETE", f"/api/clientes/{id_juridica}", admin)
chequear("Borra el segundo -> 204", codigo == 204, str(codigo))

codigo, datos = pedir("DELETE", "/api/clientes/99999", admin)
chequear("Borrar inexistente -> 404", codigo == 404, str(codigo))

# ---------------------------------------------------------------- cierre
fallidos = [r for r in resultado if not r[1]]
for nombre, ok, detalle in resultado:
    print(f"  {'OK  ' if ok else 'FALL'}  {nombre}" + (f"   -> {detalle}" if not ok and detalle else ""))
print(f"\n{len(resultado) - len(fallidos)}/{len(resultado)} pruebas pasaron")
if fallidos:
    raise SystemExit(1)
