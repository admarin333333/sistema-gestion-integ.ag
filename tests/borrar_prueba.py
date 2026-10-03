"""Borrar datos de PRUEBA, y solo de prueba. Para que las suites no lleven la
base del estudio por delante.

**Por qué existe este archivo.** Varias suiteslimptaban así:

```python
db.execute(text("DELETE FROM asientos"))
db.execute(text("DELETE FROM comprobantes_internos"))
```

Eso no borra "lo de la prueba": borra **todos los asientos del contador**. Y
como las suites miden diferencias contra una línea de base que toman DESPUÉS de
limpiar, el borrado nunca se nota: los tests dan 1219 verdes con la base vacía
y también los dan con la base llena. El defecto es invisible para un test que
solo mira sus propios números.

Acá está la regla que usan todas: **se borra lo que esta suite creó, y nada
más**. Un test no puede borrar lo que el contador cargó.

La marca de "esto es de prueba" se busca en el dato, nunca en el nombre de la
tabla:

  - el **punto de venta** de las facturas de prueba (9900, 9955, ...): es un
    número reservado, imposible que un contador lo use;
  - el **concepto** que dice "PRUEBA" adentro;
  - los **CUIT/DNI de prueba** (ver `CUITS_PRUEBA`), para las personas.
"""

from sqlalchemy import text

# Los puntos de venta que las suites usan para sus facturas. Son números altos y
# raros a propósito: si alguno aparece en una factura del contador, es que el
# contador lo eligió, y entonces esa factura NO se toca.
PUNTOS_VENTA_PRUEBA = ("9900", "9955", "9901", "9960", "9970")

# CUIT y DNI que usan las suites para crear clientes. Mismo criterio: son de
# prueba por definición, están en una lista explícita.
CUITS_PRUEBA = (
    "20301234567", "20309876543", "20298765432", "20123456789",
    "27301234567", "27098765432", "20345678901", "20234567890",
    "33712345678", "30712345678", "20356789012", "20267890123",
    "20345678912", "20245678901", "27234567890", "27245678901",
)

# Con estos DNI/CUIT el limpiador `limpiar_clientes_prueba.py` ya sabe qué es
# basura de las corridas anteriores.
DNI_PRUEBA = (
    "39888777", "39777666", "30111222", "30222333", "30333444", "30444555",
    # 39777666 y 39777667 son el mismo cliente de prueba con dos personas (la
    # suite crea una y después otra). Faltaba el segundo, y su factura con
    # asiento se quedaba dando vueltas.
    "39777667",
)


def _es_marca(texto: str | None) -> bool:
    return bool(texto) and "PRUEBA" in texto.upper()


def _ids_de_asiento_de_facturas(db, facturas_ids: list[int]) -> list[int]:
    if not facturas_ids:
        return []
    marcas = ",".join(str(i) for i in facturas_ids)
    return [
        r[0]
        for r in db.execute(
            text(f"SELECT id_asiento FROM asiento_origen WHERE id_factura IN ({marcas})")
        ).all()
    ]


def facturas_de_prueba(db) -> list[int]:
    """Las facturas que son de prueba, por TRES vías.

    - las que las suites crean con punto de venta reservado;
    - las que se reconocen por el concepto;
    - **las que son de un cliente de prueba**, que es la vía que más se
      olvida: la suite pide "el primer cliente que hay" y le carga cuatro
      facturas encima. El cliente tiene CUIT o DNI de prueba, así que se
      reconocen igual.
    """
    pv = ", ".join(f"'{p}'" for p in PUNTOS_VENTA_PRUEBA)
    por_pv = db.execute(
        text(f"SELECT id FROM facturas WHERE punto_venta IN ({pv})")
    ).all()
    por_concepto = db.execute(
        text("SELECT id FROM facturas WHERE UPPER(concepto) LIKE '%PRUEBA%'")
    ).all()
    por_cliente = db.execute(
        text(
            f"SELECT id FROM facturas WHERE cliente_id IN {sql_clientes_prueba()}"
        )
    ).all()
    return sorted(
        {r[0] for r in por_pv} | {r[0] for r in por_concepto} | {r[0] for r in por_cliente}
    )


def recibos_de_prueba(db) -> list[int]:
    """Los recibos de prueba.

    OJO: `recibos` NO tiene columna `concepto` (el comprobante es el número del
    recibo). Por eso se reconocen por su cliente: si el cliente es de prueba, el
    recibo es de prueba.
    """
    return [
        r[0]
        for r in db.execute(
            text(f"SELECT id FROM recibos WHERE cliente_id IN {sql_clientes_prueba()}")
        ).all()
    ]


def limpiar_asientos(db, facturas_ids: list[int] | None = None) -> int:
    """Borra los asientos de las facturas dadas. Devuelve cuántos borró.

    No toca el resto de los asientos: los del contador se quedan donde están.
    El orden lo manda el FK (`asiento_origen` y `aplicaciones_recibo` apuntan a
    las facturas con RESTRICT), así que primero las aplicaciones.
    """
    if facturas_ids is None:
        facturas_ids = facturas_de_prueba(db)
    if not facturas_ids:
        return 0

    marcas = ",".join(str(i) for i in facturas_ids)
    db.execute(
        text(f"DELETE FROM aplicaciones_recibo WHERE factura_id IN ({marcas})")
    )

    asientos = _ids_de_asiento_de_facturas(db, facturas_ids)
    for aid in asientos:
        db.execute(
            text("DELETE FROM asiento_detalle WHERE id_asiento = :a"), {"a": aid}
        )
        db.execute(
            text("DELETE FROM asiento_origen WHERE id_asiento = :a"), {"a": aid}
        )
        db.execute(text("DELETE FROM asientos WHERE id_asiento = :a"), {"a": aid})
    return len(asientos)


def limpiar_comprobantes(db) -> int:
    """Borra los comprobantes internos de prueba (los que dicen "PRUEBA").

    El número de cada comprobante es correlativo: si se borra uno sin querer, el
    siguiente vuelve a usar ese número y queda un hueco en la numeración que
    después nadie puede explicar.

    **Y también los huérfanos**: los comprobantes cuyo asiento ya no está, o
    cuyo documento (la factura o el recibo del concepto) fue borrado. Son
    restos de corridas anteriores que, si quedan, corren la numeración: la
    suite siguiente espera "OP-000001" y se encuentra "OP-000015", que no es un
    error del sistema sino basura de la corrida anterior.

    Los asientos que usaban esos comprobantes se van primero: `asientos` apunta
    a `comprobantes_internos` con RESTRICT, y borrar al revés MySQL corta con
    "Cannot delete or update a parent row".

    Los ids se traen a Python en vez de dejar el `DELETE` con un `IN` sobre la
    misma tabla: MySQL no lo permite ("Can't specify target table for update").
    """
    ids = [
        r[0]
        for r in db.execute(
            text(
                "SELECT c.id_comprobante FROM comprobantes_internos c "
                "WHERE UPPER(c.concepto) LIKE '%PRUEBA%' "
                "   OR NOT EXISTS (SELECT 1 FROM asientos a "
                "                  WHERE a.id_comprobante = c.id_comprobante)"
            )
        ).all()
    ]
    if not ids:
        return 0

    marcas = ",".join(str(i) for i in ids)
    for (aid,) in db.execute(
        text(f"SELECT id_asiento FROM asientos WHERE id_comprobante IN ({marcas})")
    ).all():
        db.execute(text("DELETE FROM asiento_origen WHERE id_asiento = :a"), {"a": aid})
        db.execute(text("DELETE FROM asiento_detalle WHERE id_asiento = :a"), {"a": aid})
        db.execute(text("DELETE FROM asientos WHERE id_asiento = :a"), {"a": aid})

    r = db.execute(text(f"DELETE FROM comprobantes_internos WHERE id_comprobante IN ({marcas})"))
    return r.rowcount


def limpiar_todo(db) -> dict:
    """Limpieza de arranque: lo que dejaron corridas anteriores.

    Se llama al principio de cada suite para que sean reentrantes. Solo toca
    facturas, asientos y comprobantes con marca de prueba.

    El orden lo manda el FK, y es el que cuesta acordarse:
    `asiento_origen` apunta a la factura/recibo con RESTRICT, así que los
    asientos tienen que irse ANTES que el documento. Si se hace al revés, MySQL
    dice "Cannot delete or update a parent row" y la suite se cae.
    """
    limpiar_comprobantes(db)
    facturas = facturas_de_prueba(db)
    recibos = recibos_de_prueba(db)

    # --- los asientos de esos documentos, y su detalle ------------------
    for columna, ids in (("id_factura", facturas), ("id_recibo", recibos)):
        if not ids:
            continue
        marcas = ",".join(str(i) for i in ids)
        for (aid,) in db.execute(
            text(f"SELECT id_asiento FROM asiento_origen WHERE {columna} IN ({marcas})")
        ).all():
            db.execute(
                text("DELETE FROM asiento_detalle WHERE id_asiento = :a"), {"a": aid}
            )
            db.execute(
                text("DELETE FROM asiento_origen WHERE id_asiento = :a"), {"a": aid}
            )
            db.execute(text("DELETE FROM asientos WHERE id_asiento = :a"), {"a": aid})

    # --- los recibos ------------------------------------------------------
    if recibos:
        marcas = ",".join(str(i) for i in recibos)
        db.execute(
            text(f"DELETE FROM aplicaciones_recibo WHERE recibo_id IN ({marcas})")
        )
        db.execute(text(f"DELETE FROM recibo_pagos WHERE recibo_id IN ({marcas})"))
        db.execute(text(f"DELETE FROM recibos WHERE id IN ({marcas})"))

    asientos = limpiar_asientos(db, facturas)
    comprobantes = limpiar_comprobantes(db)

    if facturas:
        marcas = ",".join(str(i) for i in facturas)
        db.execute(text(f"DELETE FROM facturas WHERE id IN ({marcas})"))

    db.commit()
    return {
        "facturas": len(facturas),
        "recibos": len(recibos),
        "asientos": asientos,
        "comprobantes": comprobantes,
    }


def contar_asientos(db) -> tuple[int, int]:
    """(asientos totales, asientos de prueba). Para que una suite verifique
    al terminar que dejó los reales donde estaban.

    Esta es la prueba que faltaba y que habría detectado el problema: si
    `total_antes` y `total_despues` no dan lo mismo, la suite se comió algo que
    no era suyo.
    """
    total = db.execute(text("SELECT COUNT(*) FROM asientos")).scalar() or 0
    de_prueba = db.execute(
        text("SELECT COUNT(*) FROM asientos WHERE UPPER(concepto) LIKE '%PRUEBA%'")
    ).scalar() or 0
    return total, de_prueba


# =====================================================================
# LA HUELLA DIGITAL
# =====================================================================
#
# Un conteo no sirve: los tests borran sus propios restos, así que una caída en
# el número de filas puede ser lo normal o puede ser unadala. Lo que importa es
# **qué filas desaparecieron**, y eso se mide con la clave primaria de cada una.
#
# `huella()` devuelve, por tabla, el conjunto de claves primarias que NO son
# de prueba. Si después de correr los tests falta alguna, esa fila la perdía
# una suite.

# Las tablas que los tests tocan a propósito. Sus filas de prueba se excluyen
# una por una con las marcas de arriba; lo que queda en la huella es lo del
# contador, y eso es lo que no se puede perder.
TABLAS_DE_OPERACION = {
    "asientos", "asiento_detalle", "asiento_origen", "comprobantes_internos",
    "facturas", "recibos", "compras", "recibo_pagos", "aplicaciones_recibo",
    "anticipos", "aplicaciones_anticipo", "personas", "clientes", "proveedores",
    "plan_cuentas", "ejercicios", "periodos",
}


def claves_primarias(db) -> dict[str, str]:
    """La clave primaria de cada tabla, preguntándoselo a MySQL.

    La primera versión tenía la lista escrita a mano y se equivocaba en cuatro
    o cinco tablas (`asiento_origen` es `id_origen`, no `id`;
    `config_cuentas_forma_pago` no tiene `codigo`...). Es la misma lección del
    respaldo: **una lista escrita a mano se queda vieja sola**. MySQL la tiene
    a mano, así que se la preguntamos.
    """
    return {
        r[0]: r[1]
        for r in db.execute(
            text(
                "SELECT TABLE_NAME, COLUMN_NAME FROM information_schema."
                "KEY_COLUMN_USAGE WHERE TABLE_SCHEMA = DATABASE() "
                "AND CONSTRAINT_NAME = 'PRIMARY'"
            )
        ).all()
    }


def huella(db) -> dict[str, set]:
    """Las filas de datos REALES, por tabla, como conjunto de claves primarias.

    "Reales" = todo lo que no se reconoce como prueba por las marcas de arriba
    (punto de venta reservado, "PRUEBA" en el concepto, CUIT de prueba). Es lo
    que el contador cargó y lo que no se puede perder.

    Para las tablas sin clave primaria se mide por cantidad: no se puede decir
    qué filas faltan, pero sí detectar que la tabla entera se vació, que es el
    caso grave.
    """
    tablas = [
        r[0]
        for r in db.execute(
            text("SELECT TABLE_NAME FROM information_schema.TABLES "
                 "WHERE TABLE_SCHEMA = DATABASE()")
        ).all()
    ]
    pk = claves_primarias(db)

    # Todo lo que las suites reconocen como basura, en un conjunto por tabla.
    pruebas = _ids_de_prueba(db)

    salida: dict[str, set] = {}
    for t in tablas:
        clave = pk.get(t)
        if clave is None:
            salida[t] = {
                (db.execute(text(f"SELECT COUNT(*) FROM `{t}`")).scalar() or 0,)
            }
            continue
        filas = {
            r[0] for r in db.execute(text(f"SELECT `{clave}` FROM `{t}`")).all()
        }
        salida[t] = filas - pruebas.get(t, set())
    return salida


def sql_clientes_prueba() -> str:
    """`(SELECT ... )` que da los ids de los clientes de prueba.

    Va en crudo porque son valores de una lista fija del archivo, no datos que
    vengan de afuera: no hay por qué parameterizar algo que no puede cambiar.
    """
    cuits = ",".join(f"'{c}'" for c in CUITS_PRUEBA)
    dnis = ",".join(f"'{d}'" for d in DNI_PRUEBA)
    return (
        f"(SELECT c.id FROM clientes c JOIN personas p ON p.id = c.persona_id "
        f"WHERE p.cuit IN ({cuits}) OR p.dni IN ({dnis}))"
    )


def sql_personas_prueba() -> str:
    """`(SELECT ... )` que da los ids de las personas de prueba."""
    cuits = ",".join(f"'{c}'" for c in CUITS_PRUEBA)
    dnis = ",".join(f"'{d}'" for d in DNI_PRUEBA)
    return f"(SELECT id FROM personas WHERE cuit IN ({cuits}) OR dni IN ({dnis}))"


def _ids_de_prueba(db) -> dict[str, set]:
    """Las filas que SÍ son de prueba, por tabla. Para restarlas de la huella."""
    fuera: dict[str, set] = {}

    def sumar(tabla, ids):
        if ids:
            fuera.setdefault(tabla, set()).update(ids)

    pv = ", ".join(f"'{p}'" for p in PUNTOS_VENTA_PRUEBA)
    # OJO: se usa la MISMA función que la limpieza, no una lista propia. Antes
    # cada una tenía su criterio y se contradecían: la limpieza borraba las
    # facturas de un cliente de prueba y la huella las contaba como reales, así
    # que la corrida se cortaba diciendo que se habían perdido datos que en
    # realidad acababa de borrar la propia suite.
    sumar("facturas", facturas_de_prueba(db))
    sumar(
        "recibos",
        [
            r[0]
            for r in db.execute(
                text(f"SELECT id FROM recibos WHERE cliente_id IN {sql_clientes_prueba()}")
            ).all()
        ],
    )
    sumar(
        "asientos",
        [
            r[0]
            for r in db.execute(
                text("SELECT id_asiento FROM asientos WHERE UPPER(concepto) LIKE '%PRUEBA%'")
            ).all()
        ],
    )
    # Los asientos "colgados": su comprobante interno ya no existe, así que no
    # son de ningún documento del contador. Siempre son restos de una corrida
    # cortada a mitad.
    sumar(
        "asientos",
        {
            r[0]
            for r in db.execute(
                text(
                    "SELECT a.id_asiento FROM asientos a "
                    "WHERE a.id_comprobante IS NOT NULL AND NOT EXISTS "
                    "(SELECT 1 FROM comprobantes_internos c "
                    " WHERE c.id_comprobante = a.id_comprobante)"
                )
            ).all()
        },
    )
    # Los asientos que salen de esas facturas.
    facturas_prueba = fuera.get("facturas", set())
    if facturas_prueba:
        marcas = ",".join(str(i) for i in facturas_prueba)
        sumar(
            "asientos",
            [
                r[0]
                for r in db.execute(
                    text(f"SELECT id_asiento FROM asiento_origen "
                         f"WHERE id_factura IN ({marcas})")
                ).all()
            ],
        )
    sumar(
        "asiento_detalle",
        {
            r[0]
            for r in db.execute(
                text(
                    "SELECT d.id_detalle FROM asiento_detalle d "
                    "LEFT JOIN asientos a ON a.id_asiento = d.id_asiento "
                    "WHERE a.id_asiento IS NULL"
                )
            ).all()
        },
    )
    # Un comprobante interno es de prueba si su concepto lo dice, o si el asiento
    # que lo usaba ya no está.
    #
    # La segunda vía es la que importa: los tests crean comprobantes (RC-000010
    # y compañía) que quedan colgados de asientos que la suite ya borró. Si la
    # huella los contara como reales, cortaría la corrida diciendo "se perdió un
    # comprobante" cuando lo que se perdió fue la prueba.
    sumar(
        "comprobantes_internos",
        [
            r[0]
            for r in db.execute(
                text(
                    "SELECT c.id_comprobante FROM comprobantes_internos c "
                    "WHERE UPPER(c.concepto) LIKE '%PRUEBA%' "
                    "   OR NOT EXISTS (SELECT 1 FROM asientos a "
                    "                   WHERE a.id_comprobante = c.id_comprobante)"
                )
            ).all()
        ],
    )
    sumar(
        "compras",
        [
            r[0]
            for r in db.execute(
                text("SELECT id FROM compras WHERE UPPER(concepto) LIKE '%PRUEBA%'")
            ).all()
        ],
    )
    sumar(
        "plan_cuentas",
        [
            r[0]
            for r in db.execute(
                text("SELECT id_cuenta FROM plan_cuentas "
                     "WHERE UPPER(nombre) LIKE '%PRUEBA%' "
                     "OR UPPER(nombre) LIKE '%DE PRUEBA%'")
            ).all()
        ],
    )
    sumar(
        "personas",
        [
            r[0]
            for r in db.execute(
                text(f"SELECT id FROM personas WHERE id IN {sql_personas_prueba()}")
            ).all()
        ],
    )
    # Los clientes cuelgan de las personas de prueba (persona_id).
    sumar(
        "clientes",
        [
            r[0]
            for r in db.execute(
                text(f"SELECT id FROM clientes WHERE id IN {sql_clientes_prueba()}")
            ).all()
        ],
    )

    # Los asientos que salen de esas facturas, y su detalle.
    facturas_prueba = fuera.get("facturas", set())
    if facturas_prueba:
        marcas = ",".join(str(i) for i in facturas_prueba)
        sumar(
            "asientos",
            [
                r[0]
                for r in db.execute(
                    text(f"SELECT id_asiento FROM asiento_origen "
                         f"WHERE id_factura IN ({marcas})")
                ).all()
            ],
        )
    sumar(
        "asiento_origen",
        {
            r[0] for r in db.execute(text("SELECT id_origen FROM asiento_origen")).all()
        },
    )
    return fuera


def comparar(antes: dict[str, set], despues: dict[str, set]) -> list[str]:
    """Las filas reales que desaparecieron. Vacío = nadie rompió nada."""
    perdidas = []
    for tabla, ids_antes in antes.items():
        ids_despues = despues.get(tabla, set())
        faltan = ids_antes - ids_despues
        if faltan:
            muestra = sorted(faltan)[:5]
            mas = f" (+{len(faltan) - 5} más)" if len(faltan) > 5 else ""
            perdidas.append(
                f"{tabla}: {len(faltan)} fila(s) {muestra}{mas}"
            )
    return perdidas