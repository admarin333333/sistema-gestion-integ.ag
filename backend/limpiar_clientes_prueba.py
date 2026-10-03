"""Limpia los clientes de prueba que quedaron de corridas anteriores.

Los tests crean clientes con CUIT fijo. Cuando una corrida se corta a mitad,
quedan colgados con sus facturas, y la corrida siguiente falla al querer crear
los mismos (409 "Ya existe Factura B 0001-00000042").

Sólo toca personas/clientes cuyos datos son claramente de un test: nombre
"Prueba"/"Anticipa" Y el CUIT de la lista de abajo. **A los clientes reales no
les toca**, aunque su factura pueda tener el mismo número.

Antes de borrar deja un respaldo SQL en la carpeta del backend.

Uso:  python -X utf8 limpiar_clientes_prueba.py --ver    (solo muestra)
      python -X utf8 limpiar_clientes_prueba.py
"""

import sys
from datetime import date

from sqlalchemy import text

from app.database import engine

# CUITs que usan los tests, fijos. Un cliente real no se da de alta con el mismo
# CUIT que la prueba, así que el cruzamiento es seguro.
CUITS_PRUEBA = (
    "39888777", "39888778",   # facturas
    "31999888",               # envío de mail
    "39666555", "39666556",   # anticipos
    "39777666", "39777667",   # recibos
    "30111222", "31555666",   # separación clientes/proveedores
)

# Para limpiar en orden y no chocar con los FK.
# El orden importa: primero los hijos (aplicaciones, asientos, comprobantes),
# después la factura, después el cliente, al final la persona.
#
# OJO con los asientos: una factura genera el suyo solo, así que hay que
# borrar también su comprobante y su asiento. Si no, el próximo
# `test_asientos_automaticos` choca con "El recibo ya tenía asiento".
ORDEN = [
    # 1. La tabla puente que liga factura <-> asiento y recibo <-> asiento
    "DELETE FROM asiento_origen WHERE id_factura IN ({facturas})",
    "DELETE FROM asiento_origen WHERE id_recibo IN ({recibos})",
    # 2. Los asientos y comprobantes de ESAS facturas y recibos
    "DELETE FROM asientos WHERE id_asiento IN ({asientos})",
    "DELETE FROM comprobantes_internos WHERE id_comprobante IN ({comprobantes})",
    # 3. Aplicaciones de recibos y anticipos
    "DELETE FROM aplicaciones_recibo WHERE factura_id IN ({facturas})",
    "DELETE FROM aplicaciones_recibo WHERE recibo_id IN ({recibos})",
    "DELETE FROM aplicaciones_anticipo WHERE factura_id IN ({facturas})",
    # 4. Las tablas que cuelgan del cliente que todavía no se borraron
    "DELETE FROM cliente_servicio WHERE cliente_id IN ({clientes})",
    "DELETE FROM sugerencias WHERE cliente_id IN ({clientes})",
    "DELETE FROM bal_rt54_ejercicios WHERE cliente_id IN ({clientes})",
    # 5. Las facturas y los recibos
    "DELETE FROM facturas WHERE cliente_id IN ({clientes})",
    "DELETE FROM recibos WHERE cliente_id IN ({clientes})",
    "DELETE FROM anticipos WHERE cliente_id IN ({clientes})",
    # 6. El cliente, el proveedor que se haya hecho con esa persona, y la
    #    persona. `clave_fiscal_historial` va antes de la persona.
    "DELETE FROM proveedores WHERE persona_id IN ({personas})",
    "DELETE FROM clave_fiscal_historial WHERE persona_id IN ({personas})",
    "DELETE FROM clientes WHERE id IN ({clientes})",
    "DELETE FROM personas WHERE id IN ({personas})",
]


def buscar(conn):
    """(personas, clientes) de prueba. Busca por CUIT **o por DNI**.

    Los tests no siempre dan de alta con CUIT: las personas físicas y los
    monotributistas de prueba van con DNI. Buscar solo por CUIT dejaba a todos
    esos colgados.
    """
    marcas = ",".join(f"'{c}'" for c in CUITS_PRUEBA)
    personas, clientes = [], []
    for r in conn.execute(
        text(
            f"SELECT p.id, cl.id "
            "FROM personas p LEFT JOIN clientes cl ON cl.persona_id = p.id "
            f"WHERE p.cuit IN ({marcas}) OR p.dni IN ({marcas})"
        )
    ):
        personas.append(r[0])
        if r[1]:
            clientes.append(r[1])
    return personas, clientes


def _ids(lista) -> str:
    """Lista de ids para meter en "WHERE x IN ...".

    **Sin paréntesis**: `_ids` se usa de las dos formas — pegado en los
    `WHERE ... IN {facturas}` de la lista ORDEN, y dentro de un `IN (...)` en las
    consultas de conteo. Por eso el paréntesis va en el SQL, no acá.
    """
    return ",".join(str(i) for i in lista) if lista else "0"


def respaldo(conn, personas, clientes, nombre):
    """Escribe los INSERT de lo que se va a borrar, por si acaso."""
    tablas = {
        "personas": (personas, "id"),
        "clientes": (clientes, "id"),
    }
    # Las facturas y recibos se toma por cliente.
    tablas["facturas"] = (
        [r[0] for r in conn.execute(
            text(f"SELECT id FROM facturas WHERE cliente_id IN ({_ids(clientes)})")
        )],
        "id",
    )
    tablas["recibos"] = (
        [r[0] for r in conn.execute(
            text(f"SELECT id FROM recibos WHERE cliente_id IN ({_ids(clientes)})")
        )],
        "id",
    )

    lineas = []
    for tabla, (ids, _col) in tablas.items():
        if not ids:
            continue
        columnas = [r[0] for r in conn.execute(text(f"SHOW COLUMNS FROM {tabla}"))]
        campos = ",".join(f"`{c}`" for c in columnas)
        filas = conn.execute(
            text(f"SELECT {campos} FROM {tabla} WHERE id IN ({_ids(ids)})")
        ).fetchall()
        for fila in filas:
            valores = []
            for v in fila:
                if v is None:
                    valores.append("NULL")
                elif isinstance(v, (int, float)):
                    valores.append(str(v))
                else:
                    s = str(v).replace("\\", "\\\\").replace("'", "''")
                    valores.append(f"'{s}'")
            lineas.append(f"INSERT INTO {tabla} ({campos}) VALUES ({', '.join(valores)});")

    with open(nombre, "w", encoding="utf-8") as f:
        f.write("-- Respaldo de clientes de prueba, por si alguno fuera real.\n")
        f.write(f"-- Generado el {date.today().isoformat()}\n\n")
        f.write("\n".join(lineas))
        f.write("\n")
    return len(lineas)


def main():
    solo_ver = "--ver" in sys.argv

    with engine.begin() as conn:
        personas, clientes = buscar(conn)
        if not personas:
            print("No hay clientes de prueba colgados: nada que limpiar.")
            return

        facturas = [
            r[0] for r in conn.execute(
                text(f"SELECT id FROM facturas WHERE cliente_id IN ({_ids(clientes)})")
            )
        ]
        recibos = [
            r[0] for r in conn.execute(
                text(f"SELECT id FROM recibos WHERE cliente_id IN ({_ids(clientes)})")
            )
        ]

        print(f"Personas de prueba: {len(personas)}  -> {personas}")
        print(f"Clientes de prueba: {len(clientes)}  -> {clientes}")
        print(f"Facturas a borrar:  {len(facturas)}")
        print(f"Recibos a borrar:   {len(recibos)}")
        print("\n(Borrar clientes y facturas SOLO de estos. Los reales no se tocan.)")

        if solo_ver:
            print("\n(--ver: no se borró nada)")
            return

        # Los asientos y comprobantes de esas facturas y recibos. Si no se
        # borran, quedan vivos y el próximo test choca con "ya tenía asiento".
        asientos, comprobantes = [], []
        origenes = []
        if facturas:
            origenes.append(f"id_factura IN ({_ids(facturas)})")
        if recibos:
            origenes.append(f"id_recibo IN ({_ids(recibos)})")
        if origenes:
            filas = conn.execute(
                text(
                    "SELECT DISTINCT id_asiento FROM asiento_origen WHERE "
                    + " OR ".join(origenes)
                )
            ).fetchall()
            asientos = [r[0] for r in filas]
            if asientos:
                comprobantes = [
                    r[0] for r in conn.execute(
                        text(
                            f"SELECT DISTINCT id_comprobante FROM asientos "
                            f"WHERE id_asiento IN ({_ids(asientos)}) "
                            "AND id_comprobante IS NOT NULL"
                        )
                    )
                ]
        print(f"Asientos que se borran:  {len(asientos)}")
        print(f"Comprobantes que se borran: {len(comprobantes)}")

        nombre = f"respaldos_clientes_prueba_{date.today().isoformat()}.sql"
        for i in range(2):  # si ya existe de hoy, no se pisa: _1, _2...
            try:
                with open(nombre, "x", encoding="utf-8") as _:
                    break
            except FileExistsError:
                nombre = nombre.replace(".sql", f"_{i}.sql")
        cantidad = respaldo(conn, personas, clientes, nombre)
        print(f"\nRespaldo: {nombre} ({cantidad} filas)")

        reemplazos = {
            "{facturas}": _ids(facturas),
            "{recibos}": _ids(recibos),
            "{asientos}": _ids(asientos),
            "{comprobantes}": _ids(comprobantes),
            "{clientes}": _ids(clientes),
            "{personas}": _ids(personas),
        }
        for sql in ORDEN:
            for k, v in reemplazos.items():
                sql = sql.replace(k, v)
            conn.execute(text(sql))
        print("Borrados.")

    with engine.connect() as conn:
        quedan, _ = buscar(conn)
        print(f"Quedan personas de prueba: {len(quedan)}")


if __name__ == "__main__":
    main()