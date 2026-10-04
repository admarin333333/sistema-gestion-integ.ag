"""
PREPARA LA BASE DE DATOS DE PRUEBAS.

    python -X utf8 preparar_base_prueba.py

Crea `gestion_contable_test` (o la que diga GC_TEST_DB) con el mismo esquema y los
mismos datos iniciales que la base real, y la deja **vacía de lo del contador**.

POR QUÉ EXISTE

Las 40 suites corren contra la API, y hasta ahora esa API es la que apunta a la
base de verdad. O sea: las pruebas escribían donde están los clientes, los
facturas y los asientos del estudio. Ya pasó: el 02/10/2026 una suite borró
asientos reales (ver `AGENTE.md` §6 bis). Desde entonces hay una "huella digital"
que avisa, pero **avisa después**: el daño ya está hecho y no hay vuelta atrás.

Con esta base separada, una prueba que escriba mal escribe en `_test`. Es la
diferencia entre equivocarse y perder datos.

CÓMO SE USA

Hay que levantar una API aparte, apuntando a la base de prueba:

    $env:DB_NAME = "gestion_contable_test"
    python -m uvicorn app.main:app --port 8011
    $env:GC_BASE_URL = "http://127.0.0.1:8011"
    python -X utf8 correr_todas.py

O, más fácil, doble clic en `iniciar_pruebas.bat`, que hace las tres cosas.

**No toca la base real.** Solo crea la de pruebas. Por eso el `CREATE DATABASE`
va con `IF NOT EXISTS`: correrlo de nuevo no rompe nada.
"""

import os
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "backend"))

# El nombre de la base de pruebas tiene que estar ANTES de importar `app.config`,
# porque la conexión se arma al importarlo. Por eso esto va arriba del todo.
NOMBRE_PRUEBA = os.environ.get("GC_TEST_DB", "gestion_contable_test")
os.environ["DB_NAME"] = NOMBRE_PRUEBA


def crear_base() -> None:
    """Crea la base vacía si no existe. Se conecta SIN base, solo al servidor."""
    from sqlalchemy import create_engine, text

    from app.config import settings

    # La conexión de `app.database` apunta a `db_name`, que todavía no existe: por
    # eso se arma una propia, sin nombre de base.
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
    print(f"  base `{NOMBRE_PRUEBA}` existe")


def crear_esquema_y_datos() -> None:
    """Mismo esquema y mismos datos iniciales que la base real.

    Se reutiliza `seed.main()` a propósito en vez de duplicarlo: si mañana se le
    agrega una tabla al `seed`, la base de pruebas la tiene sola. Copiarlo sería
    garantizar que en tres meses los dos schemas difieren.
    """
    import seed

    print(f"  creando tablas y datos iniciales en `{NOMBRE_PRUEBA}`...")
    seed.main()


def verificar_aislamiento() -> None:
    """
    Se comprueba que la base de pruebas **no** tiene los datos del contador.

    Es la última línea de defensa: si alguien apunta mal y termina apuntando a la
    base real, este chequeo lo dice ahora y no cuando un asiento desapareció.
    """
    from sqlalchemy import text

    from app.database import engine

    with engine.connect() as c:
        base = c.execute(text("SELECT DATABASE()")).scalar()
        facturas = c.execute(text("SELECT COUNT(*) FROM facturas")).scalar()
        clientes = c.execute(text("SELECT COUNT(*) FROM clientes")).scalar()

    print()
    print("  VERIFICACIÓN:")
    print(f"    la base conectada es: {base}")
    if base != NOMBRE_PRUEBA:
        print(f"    !!! ESTÁ CONECTADA A {base}, NO A {NOMBRE_PRUEBA}. CORREGIR.")
        raise SystemExit(1)
    print(f"    facturas: {facturas} · clientes: {clientes}")
    print(f"    (prueba limpia si son pocos o cero; hay {clientes} clientes)")


if __name__ == "__main__":
    print("Preparando la base de pruebas")
    crear_base()
    crear_esquema_y_datos()
    verificar_aislamiento()
    print()
    print("Listo. Para usarla, levantá una API contra ella:")
    print('    $env:DB_NAME = "%s"' % NOMBRE_PRUEBA)
    print("    python -m uvicorn app.main:app --port 8011")
    print('    $env:GC_BASE_URL = "http://127.0.0.1:8011"')
    print("    python -X utf8 correr_todas.py")
    print()
    print("O más fácil: doble clic en iniciar_pruebas.bat")