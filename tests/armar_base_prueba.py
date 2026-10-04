"""
ARMA LA BASE DE PRUEBAS DESDE CERO.

    python -X utf8 armar_base_prueba.py [--desde-cero]

Hace dos cosas, en este orden:

1. **El esquema lo crea Alembic** — `alembic upgrade head`, un solo comando que
   arma las 43 tablas.
2. **Los datos iniciales los cargan los scripts** — `seed.py` y los
   `migrar_*.py` queleave el plan de cuentas, el ejercicio, los períodos, los
   conceptos de vencimiento.

Al final verifica que la base tenga lo mínimo para que las pruebas pasen.

POR QUÉ ESTA SEPARACIÓN

Alembic se ocupa del ESQUEMA: qué tablas hay, qué columnas, qué índices. No de
qué datos tiene adentro, y no debería — los datos iniciales cambian según el
estudio (el ejercicio empieza en un año y otro, el plan de cuentas se puede
ajustar), mientras que el esquema es el mismo para todos.

Antes de Alembic esa división no existía: los scripts `migrar_*.py` hacían las
dos cosas a la vez. Por eso había que saber los 23 y en qué orden, y por eso dos
de ellos fallaban si la base estaba vacía.

LO QUE NO SE PISA

Los `migrar_*.py` no se borran. Los que cargan datos siguen haciendo falta; lo
que dejó de usarse son los que creaban tablas.

`--desde-cero` **borra** la base de pruebas y la vuelve a armar. Solo toca
`gestion_contable_test`: nunca la del estudio. El nombre sale de `GC_TEST_DB` y
está protegido: si apuntara al nombre de la base real, el script se frena.
"""

import os
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(RAIZ, "backend")

NOMBRE_PRUEBA = os.environ.get("GC_TEST_DB", "gestion_contable_test")
# La base del estudio. Es el nombre que hay que NUNCA tocar.
BASE_REAL = os.environ.get("GC_DB_REAL", "gestion_contable")

# EL ESQUEMA LO ARMA ALEMBIC, NO ESTA LISTA.
#
# Antes eran 16 scripts en un orden escrito a mano, y dos de ellos fallaban en
# una base limpia. `alembic upgrade head` hace los 43 tablas y además crea las
# de `config_*`, que antes no se creaban en ninguna parte: sin los tipos de
# comprobante una base nueva no puede facturar.
#
# Lo que queda acá son los scripts que cargan DATOS, que Alembic no hace (ni le
# corresponde: los datos iniciales no son esquema):
#   - `seed.py`: usuarios, localidades, alícuotas, centros, servicios
#   - `migrar_plan_cuentas.py`: el plan, que sin él no hay a dónde asentar
#   - `migrar_ejercicios.py` y `migrar_periodos.py`: el ejercicio y sus 12 meses
#   - el resto: conceptos, clave fiscal, índices, cuentas por forma de pago
#
# El orden entre estos SIGUE importando (un período pertenece a un ejercicio, el
# motor contable busca cuentas del plan), así que la lista queda. Lo que se fue
# es la parte del ESQUEMA.
ORDEN_DATOS = [
    "seed.py",
    "migrar_plan_cuentas.py",
    # Los dos que cargan las tablas de configuración. Van después del plan porque
    # las columnas `cuenta_debe`, `cuenta_haber_ingresos`... guardan el id de una
    # cuenta del plan, y el script lo busca POR CÓDIGO ("4.2.01"), no con un
    # número fijo. Por eso funcionan en cualquier base.
    #
    # `migrar_asientos_automaticos.py` carga los 8 códigos internos (FV, RC, TR...)
    # y las 5 configuraciones de asiento de venta y cobranza.
    # `migrar_notas_credito.py` agrega NC y ND y sus dos configuraciones.
    #
    # Los dos van con `ON DUPLICATE KEY UPDATE`, así que correrlos de nuevo no
    # duplica nada.
    "migrar_asientos_automaticos.py",
    "migrar_notas_credito.py",
    # `migrar_personas.py` YA NO CORRE, a propósito.
    #
    # Era la migración que partió `clientes` en `personas` + `clientes` +
    # `proveedores`: renombraba la tabla vieja, creaba las tres, pasaba los datos
    # y borraba la vieja. Todo eso es ESQUEMA, y del esquema se ocupa Alembic.
    #
    # Peor: hace daño. La primera línea hace
    # `ALTER TABLE clientes RENAME TO clientes_vieja`, o sea que al correrlo
    # renombra la tabla buena que Alembic acaba de crear y después falla al
    # recrearla. El resultado es una base sin `clientes`, y todos los scripts que
    # la necesitan (y la API entera) se rompen.
    #
    # No se borra el archivo: en una base vieja que todavía no pasó por esta
    # migración, el script sigue siendo el que hace falta.
    "migrar_ejercicios.py",
    "migrar_periodos.py",
    "migrar_conceptos_vencimiento.py",
    "migrar_clave_fiscal.py",
    # `migrar_indices_moneda.py` YA NO CORRE, a propósito. Mismo criterio que
    # `migrar_personas.py`: es ESQUEMA, no datos.
    #
    # Lo que hace es dos cosas, y ninguna es cargar datos:
    #   1) crear la tabla `config_indices_moneda`  → de eso se ocupa Alembic
    #   2) agregar `clientes.fecha_cierre_ejercicio`
    #
    # El punto 2 además está mal: esa columna está declarada en el modelo
    # `Persona`, o sea en la tabla `personas`. El script la agrega a `clientes`,
    # que es otra tabla. La base del estudio, que nunca corrió este script,
    # NO tiene la columna en `clientes` (comprobado). Correrlo en la base de
    # pruebas dejaba una columna de más que en el estudio no existe.
    #
    # OJO: los 404 índices de moneda NO están en ningún archivo del proyecto.
    # Viven solo en la base del estudio. Ver la comparación al final del script:
    # la tabla sale con 0 filas. Eso NO lo arregla este script.
    "migrar_cuenta_cobro_fija.py",
    "migrar_cuentas_forma_pago.py",
    "migrar_propietario.py",
    "migrar_motor_contable.py",
    # El nombre de este está mal en la lista desde antes: no existe
    # `migrar_compras.py`. El archivo se llama `migrar_compra_cuenta_gasto.py` y
    # además de la columna `compras.cuenta_gasto_id` carga el comprobante FP
    # (Factura de proveedor). Sin él, la base nueva queda con 10 tipos de
    # comprobante en vez de 11, y sin FP no se puede registrar una compra.
    "migrar_compra_cuenta_gasto.py",
    "migrar_vencimientos_meses.py",
    "migrar_iva_ventas.py",
    "migrar_cuentas_bancarias.py",
]


def armar_esquema_con_alembic():
    """
    Crea TODAS las tablas con `alembic upgrade head`.

    Reemplaza a los 16 scripts que se corrían a mano. La diferencia no es de
    cantidad de líneas sino de garantías: `alembic upgrade head` crea el esquema
    **que dicen los modelos**, así que una base nueva nunca nace con una tabla
    desactualizada. Con la lista a mano, el día que se agrega una columna el
    script viejo se olvida y la base nueva nace incompleta.
    """
    print("  creando el esquema con Alembic...")
    r = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=BACKEND,
        env=entorno(),
        timeout=600,
    )
    if r.returncode != 0:
        print("    X alembic upgrade head falló:")
        for linea in (r.stderr or r.stdout).strip().splitlines()[-6:]:
            print("      " + linea)
        return False
    print("    ok esquema creado")
    return True


def entorno():
    e = dict(os.environ)
    e["DB_NAME"] = NOMBRE_PRUEBA
    return e


def correr(nombre, argumentos=()):
    """Corre un script de datos. Devuelve True si terminó bien.

    **Si el archivo no existe, se frena.** Antes imprimía `? no existe, lo salto`
    y seguía, que es la peor forma de fallar: uno lee "todo ok" y en realidad le
    falta un script entero. En una lista corta y escrita a mano, un nombre mal
    es un error de tipeo, no algo que haya que tolerar.

    La lista tiene 17 entradas y la base de pruebas se arma con esto. Si un
    nombre está mal, la base queda incompleta y las pruebas empiezan a fallar
    una por una, con errores que no dicen nada sobre la causa.
    """
    ruta = os.path.join(BACKEND, nombre)
    if not os.path.exists(ruta):
        print(f"    X {nombre} NO EXISTE")
        print()
        print(f"  Me freno: la lista dice que hay que correr {nombre} y no está")
        print(f"  en {ruta}.")
        print()
        print("  Puede ser que:")
        print(f"    - el nombre está mal escrito en ORDEN_DATOS, o")
        print("    - el script se renombró y la lista quedó vieja.")
        print()
        print("  No lo salteo a propósito: seguir sin él arma una base incompleta")
        print("  y las pruebas después fallan con errores que no explican nada.")
        return False

    r = subprocess.run(
        [sys.executable, "-X", "utf8", ruta, *argumentos],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=BACKEND,
        env=entorno(),
        timeout=300,
    )
    if r.returncode != 0:
        primera = (r.stderr or r.stdout or "").strip().splitlines()
        ultimo = primera[-1][:100] if primera else "sin mensaje"
        print(f"    X {nombre}: {ultimo}")
        return False
    return True


def borrar_base():
    """Tira la base de pruebas y la vuelve a crear vacía."""
    from sqlalchemy import create_engine, text

    sys.path.insert(0, BACKEND)
    from app.config import settings

    if NOMBRE_PRUEBA == BASE_REAL:
        print("  !!! El nombre de la base de pruebas es el de la base REAL.")
        print("  !!! Me freno acá: no toco la base del estudio.")
        raise SystemExit(1)

    url = (
        f"mysql+pymysql://{settings.db_user}:{settings.db_password}"
        f"@{settings.db_host}:{settings.db_port}"
    )
    motor = create_engine(url)
    with motor.connect() as c:
        c.execute(text(f"DROP DATABASE IF EXISTS `{NOMBRE_PRUEBA}`"))
    motor.dispose()
    print(f"  base `{NOMBRE_PRUEBA}` borrada")


def verificar():
    """
    Que la base tenga lo mínimo para que las pruebas pasen.

    **La conexión se arma A MANO, con el nombre de la base de pruebas, y no con
    `app.database`.** Es a propósito: `app.database` se importa una sola vez y
    queda con la base que tenía en el entorno al importarse. Si el script corrió
    las migraciones primero (que importan ese módulo), después el `DB_NAME` que
    se pone acá llega tarde y la verificación va a mirar la base del estudio.

    Es exactamente lo que pasó la primera vez: la verificación se conectó a
    `gestion_contable` y el chequeo de seguridad no sirvió de nada porque se hizo
    tarde. Por eso la conexión va aparte.
    """
    from sqlalchemy import create_engine, text

    sys.path.insert(0, BACKEND)
    from app.config import settings

    url_prueba = (
        f"mysql+pymysql://{settings.db_user}:{settings.db_password}"
        f"@{settings.db_host}:{settings.db_port}/{NOMBRE_PRUEBA}"
    )
    motor = create_engine(url_prueba)

    checks = [
        ("tablas", "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA=DATABASE()", 40),
        ("usuarios", "SELECT COUNT(*) FROM usuarios", 2),
        ("plan de cuentas", "SELECT COUNT(*) FROM plan_cuentas", 50),
        ("ejercicios", "SELECT COUNT(*) FROM ejercicios", 1),
        ("periodos", "SELECT COUNT(*) FROM periodos", 12),
        ("conceptos venc.", "SELECT COUNT(*) FROM conceptos_vencimiento", 5),
        ("localidades", "SELECT COUNT(*) FROM localidades", 80),
        ("alicuotas", "SELECT COUNT(*) FROM alicuotas_iva", 3),
        # Las de configuración. Sin los tipos de comprobante no se puede facturar:
        # el formulario no tiene qué mostrar y la API rechaza la factura. Es el
        # motivo por el que la base nueva tiene que traerlas.
        ("tipos comprobante", "SELECT COUNT(*) FROM config_comprobantes", 10),
        ("formas de pago", "SELECT COUNT(*) FROM config_cuentas_forma_pago", 5),
        ("config de asientos", "SELECT COUNT(*) FROM config_asientos", 7),
        ("cuenta cobro fija", "SELECT COUNT(*) FROM config_sistema WHERE clave='cuenta_cobro_fija'", 1),
    ]

    print()
    print("  VERIFICACIÓN:")
    problemas = 0
    with motor.connect() as c:
        base = c.execute(text("SELECT DATABASE()")).scalar()
        print(f"    base conectada: {base}")
        if base != NOMBRE_PRUEBA:
            print(f"    !!! Debería ser {NOMBRE_PRUEBA}")
            problemas += 1

        for nombre, sql, minimo in checks:
            n = c.execute(text(sql)).scalar()
            bien = n >= minimo
            if not bien:
                problemas += 1
            marca = "ok " if bien else "FALTA"
            print(f"    {marca} {nombre:18} {n} (se esperan {minimo}+)")

    motor.dispose()
    return problemas


# --------------------------------------------------------------------------
# Comparación con la base del estudio
# --------------------------------------------------------------------------
#
# Cada tabla dice por qué se compara así:
#
#   tabla                       se compara por      porque
#   --------------------------  ------------------  -----------------------------
#   config_sistema              clave               clave/valor, no id
#   config_comprobantes         codigo              el id es autoincremental
#   config_cuentas_forma_pago   forma_pago          id va incluido pero no se usa
#   config_asientos             clave               id autoincremental
#   config_indices_moneda       fecha               un índice por mes
#
# POR QUÉ NO SE COMPARA EL `id`
#
# El `id` de estas tablas es AUTO_INCREMENT y no tiene por qué ser el mismo en
# las dos bases: depende del orden en que se cargó cada una. Comparar el id
# daría 404 diferencias en `config_indices_moneda` que no quieren decir nada.
# Lo que importa es que estén las MISMAS filas con el Mismo contenido.
#
# Y las CUENTAS se comparan por su código, no por su id, por la misma razón: el
# plan de cuentas también se numera solo, así que el `id` 96 puede ser una cuenta
# en una base y otra en la otra. El código ("1.1.03.02") sí es el mismo.
COMPARACIONES = [
    {
        "tabla": "config_sistema",
        "clave": "clave",
        "columnas": ["clave", "valor"],
        "cuentas": [],
    },
    {
        "tabla": "config_comprobantes",
        "clave": "codigo",
        "columnas": ["codigo", "nombre", "origen", "activa"],
        "cuentas": [],
    },
    {
        "tabla": "config_cuentas_forma_pago",
        "clave": "forma_pago",
        "columnas": ["forma_pago", "requiere_banco"],
        "cuentas": ["cuenta_id"],
    },
    {
        "tabla": "config_asientos",
        "clave": "clave",
        "columnas": ["clave", "nombre", "activa"],
        "cuentas": [
            "cuenta_debe",
            "cuenta_haber_ingresos",
            "cuenta_haber_iva",
            "cuenta_haber_cobranza",
        ],
    },
    {
        "tabla": "config_indices_moneda",
        "clave": "fecha",
        "columnas": ["fecha", "indice"],
        "cuentas": [],
    },
]


def _leer_config(motor, tabla, por_clave, columnas, cuentas):
    """
    Lee una tabla de configuración y la devuelve como lista de tuplas.

    Cada columna de cuenta se resuelve con un SUBSELECT que trae el código de
    `plan_cuentas`.

    Por qué subselect y no un JOIN: `config_asientos` tiene CUATRO columnas de
    cuenta (`cuenta_debe`, `cuenta_haber_ingresos`, `cuenta_haber_iva`,
    `cuenta_haber_cobranza`) y cada una apunta a una cuenta distinta. Un solo
    JOIN no alcanza —harían falta cuatro, cada uno con su alias— y con cuatro
    filas por asiento la lectura se vuelve un enredo. El subselect es
    independiente por columna y no multiplica filas.

    Si el id es NULL o no existe ninguna cuenta con ese id, queda `<sin>`.
    """
    from sqlalchemy import text

    seleccion = [f"t.{c}" for c in columnas]
    seleccion += [
        "(SELECT codigo FROM plan_cuentas WHERE id_cuenta = t." + col + ") "
        "AS " + col
        for col in cuentas
    ]

    sql = (
        f"SELECT {', '.join(seleccion)} FROM {tabla} t ORDER BY t.{por_clave}"
    )
    with motor.connect() as c:
        return [tuple(r) for r in c.execute(text(sql)).all()]


def comparar_config():
    """
    Compara las 5 tablas `config_*` de la base de pruebas contra las de la real.

    Solo LEE de la base del estudio. Jamás escribe ni una fila ahí: para eso está
    el `DROP` protegido de `borrar_base()`.

    Devuelve la cantidad de diferencias, para que `main()` pueda decidir si
    frena. Y la imprime, porque un número solo no dice nada: hay que ver
    QUÉ fila se parece a cuál.
    """
    from sqlalchemy import create_engine

    sys.path.insert(0, BACKEND)
    from app.config import settings

    base = (
        f"mysql+pymysql://{settings.db_user}:{settings.db_password}"
        f"@{settings.db_host}:{settings.db_port}/"
    )
    motor_real = create_engine(base + BASE_REAL)
    motor_prueba = create_engine(base + NOMBRE_PRUEBA)

    print()
    print(f"  COMPARACIÓN CON LA BASE DEL ESTUDIO ({BASE_REAL}):")
    print(f"    {NOMBRE_PRUEBA}  ←→  {BASE_REAL}")
    print()

    diferencias = 0

    for spec in COMPARACIONES:
        tabla = spec["tabla"]
        por_clave = spec["clave"]
        columnas = spec["columnas"]
        cuentas = spec["cuentas"]

        real = _leer_config(motor_real, tabla, por_clave, columnas, cuentas)
        prueba = _leer_config(motor_prueba, tabla, por_clave, columnas, cuentas)

        encuadre = "igual" if real == prueba else "DIFIERE"
        marca = "ok " if real == prueba else ">>>"
        print(
            f"    {marca} {tabla:28} {len(prueba):4} fila(s) en pruebas "
            f"| {len(real):4} en la real   {encuadre}"
        )

        if real == prueba:
            continue

        diferencias += 1

        # Se listan por clave, no fila por fila: `config_indices_moneda` tiene
        # 404 y una diferencia de un dígito no se lee en 400 líneas.
        claves_real = {r[0]: r for r in real}
        claves_prueba = {r[0]: r for r in prueba}

        solo_real = sorted(set(claves_real) - set(claves_prueba))
        solo_prueba = sorted(set(claves_prueba) - set(claves_real))

        # Mismo conjunto de claves pero distinto contenido.
        distintas = [
            k for k in claves_prueba
            if k in claves_real and claves_prueba[k] != claves_real[k]
        ]

        def mostrar(etiqueta, claves, fuente):
            """Imprime hasta 8 claves y después el resumen."""
            for k in claves[:8]:
                print(f"        {etiqueta:16} {k}: {fuente[k][1:]}")
            if len(claves) > 8:
                print(
                    f"        {'':16} ... y {len(claves) - 8} más "
                    f"(total {len(claves)})"
                )

        mostrar("solo en la REAL", solo_real, claves_real)
        mostrar("solo en PRUEBAS", solo_prueba, claves_prueba)

        for k in sorted(distintas)[:8]:
            print(f"        DISTINTA {k}")
            print(f"          en PRUEBAS: {claves_prueba[k][1:]}")
            print(f"          en la REAL: {claves_real[k][1:]}")
        if len(distintas) > 8:
            print(f"        ... y {len(distintas) - 8} filas más con distinto valor")

        if not solo_real and not solo_prueba and not distintas:
            # Mismo contenido, distinto orden: no es una diferencia real.
            print("        (solo cambió el orden de las filas)")

    motor_real.dispose()
    motor_prueba.dispose()

    return diferencias


if __name__ == "__main__":
    desde_cero = "--desde-cero" in sys.argv

    print("Armando la base de pruebas")
    print(f"  base: {NOMBRE_PRUEBA}")
    print()

    if desde_cero:
        borrar_base()

    sys.path.insert(0, BACKEND)
    os.environ["DB_NAME"] = NOMBRE_PRUEBA

    # Crear la base si no existe (sin esto, seed falla la primera vez).
    from sqlalchemy import create_engine, text

    from app.config import settings

    url_sin_base = (
        f"mysql+pymysql://{settings.db_user}:{settings.db_password}"
        f"@{settings.db_host}:{settings.db_port}"
    )
    motor = create_engine(url_sin_base)
    with motor.connect() as c:
        c.execute(
            text(
                f"CREATE DATABASE IF NOT EXISTS `{NOMBRE_PRUEBA}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        )
    motor.dispose()

    print("  Aplicando seed y migraciones:")
    if not armar_esquema_con_alembic():
        print("  Sin esquema no hay base. Me freno.")
        raise SystemExit(1)

    print()
    print("  Cargando los datos iniciales:")
    # Se corta en el primer script que falla. Seguir significa armar una base a
    # medias y recién enterarse en la verificación, o peor, en las pruebas.
    for nombre in ORDEN_DATOS:
        if not correr(nombre):
            print()
            print(f"  {nombre} falló. No sigo con los que faltan.")
            print("  La base quedó incompleta. Volvé a correrlo cuando lo arregles.")
            raise SystemExit(1)
        print(f"    ok {nombre}")

    problemas = verificar()

    print()
    if problemas:
        print(f"  Faltan {problemas} cosas. Las pruebas van a fallar.")
        raise SystemExit(1)

    diferencias = comparar_config()

    print()
    if diferencias:
        print(f"  Las tablas config_* difieren de la base del estudio en "
              f"{diferencias} tabla(s).")
        print("  No es necesariamente un error: la base del estudio puede tener")
        print("  correcciones a mano que los scripts no reproducen (ver arriba).")
        print("  Revisá si lo que falta es algo que las pruebas necesiten.")
    else:
        print("  Las 5 tablas config_* quedaron IGUALES a las del estudio.")

    print()
    print("  La base de pruebas está lista.")
    print()
    print("  Para correr las pruebas:")
    print('    $env:GC_BASE_URL = "http://127.0.0.1:8011"')
    print("    python -X utf8 correr_todas.py")
    print("  O doble clic en tests\\iniciar_pruebas.bat")