"""
Alembic — migración del esquema de la base de datos.

QUÉ CAMBIA RESPECTO DE LOS `migrar_*.py` SUELTOS

Hasta ahora el esquema se evolucionaba con 23 scripts independientes en
`backend/`. El problema no es que fueran incorrectos: varios están bien hechos e
idempotentes. El problema es que **nadie sabía en qué versión estaba una base**.
Para saberlo había que acordarse de qué scripts se habían corrido.

Alembic lo resuelve con la tabla `alembic_version`: una fila con el número de
revisión a la que llegó la base. `alembic current` dice en qué versión está.

CÓMO SE USA

    alembic upgrade head              aplicar todo lo que falta
    alembic downgrade -1             volver atrás un paso
    alembic current                  en qué versión está la base
    alembic history                  lista de revisiones, en orden
    alembic revision --autogenerate -m "agregar tabla X"   crear una migración

PARA AGREGAR UNA TABLA O UNA COLUMNA

1. Se cambia el modelo (`app/models/...`)
2. `alembic revision --autogenerate -m "lo que se agregó"`
3. **Se lee el archivo generado.** El autogen tiene SymbolicOperatingError: a
   veces produce diferencias que no son lo que uno cree. Con un campo ForeignKey
   spotting lo cambia por una copia del nombre, por ejemplo.
4. Se edita lo que haga falta y recién ahí `alembic upgrade head`.

OJO CON ESTO

**`--autogenerate` NUNCA se corre solo contra la base real.** Compara el modelo
con la base y escribe lo que encuentra, y si se aplicara sin mirarlo, una
diferencia mal detectada modificaría la base de verdad. Siempre: generar, leer,
corregir si hace falta, y recién después aplicar.

**LA BASE ACTUAL YA ESTÁ "EN HEAD".** Cuando se adoptó Alembic, la base del
estudio tenía las 37 tablas y todas las columnas que el modelo pedía. No se
generó una migración "crear todo" porque no es verdad: eso habría intentado
crear tablas que ya existían. Se usó `alembic stamp head`, que solo anota la
versión sin tocar el esquema. Ver `migraciones/README`.

LO QUE SIGUE VIVIENDO EN LOS `migrar_*.py`

Los 23 scripts **no se borran**. Muchos no cambian el esquema sino los DATOS:
crean el ejercicio, los 12 períodos, el plan de cuentas, las alícuotas. Eso no es
migración de esquema, es carga inicial, y sigue living en su script.

La diferencia: a partir de ahora, **cualquier cambio de esquema va por
Alembic**, y los `migrar_*.py` solo se tocan para cosas de datos.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import settings
from app.database import Base

# Importar TODOS los modelos: sin esto, `Base.metadata` solo tiene las tablas que
# se importaron por casualidad y el autogen creería que el resto no existen.
from app import models  # noqa: F401

config = context.config

# Si hay alembic.ini con logging, se usa; si no, se sigue igual.
if config.config_file_name is not None:
    try:
        fileConfig(config.config_file_name)
    except Exception:
        pass

# El destino NO se escribe en alembic.ini: sale de `app.config`, que a su vez lo
# lee del `.env`. Así la migración va a la misma base que la aplicación, sin que
# haya que acordarse de configurarlo en dos lugares.
#
# Con esto, `DB_NAME=gestion_contable_test alembic upgrade head` migra la base
# de pruebas y la del estudio queda intacta, sin tocar el `.env`.
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata

# --------------------------------------------------------------------------
# TABLAS QUE ALEMBIC IGNORA
# --------------------------------------------------------------------------
# **Hoy está VACÍO a propósito, y eso es el objetivo.**
#
# Cuando se adoptó Alembic, estas cuatro tablas estaban en la base sin modelo
# (se usaban con SQL a mano). Para el autogen eso era una tabla sobrante y
# `--autogenerate` proponía **borrarlas**: con 11 tipos de comprobante y 6 formas
# de pago adentro, el sistema dejaba de poder facturar.
#
# La primera solución fue un `include_object` que las filtrara. Funcionaba, pero
# era una foto: mientras estuvieran en la lista nadie las veía, y una columna
# nueva en alguna no se detectaba.
#
# La definitiva fue **modelarlas** (`app/models/config.py`). Ahora Alembic las
# compara de verdad y además las crea en una base nueva.
#
# POR QUÉ LA LISTA NO SE BORRÓ SINO QUE SE DEJÓ CON LA EXPLICACIÓN
#
# Porque si algún día aparece otra tabla usada con SQL a mano, el filtro sigue
# acá para ponerla y el error se evita en un ratito. **Cada vez que se agrega un
# modelo, se saca el nombre de esta lista**, en el mismo commit.
TABLAS_FUERA = {
    # Vacío: las cuatro de `config_*` ya tienen modelo (03/10/2026).
}


def incluir_objeto(obj, name, type_, reflected, compare_to):
    """
    Le dice a Alembic que se olvide de las tablas de `TABLAS_FUERA`.

    `type_ == "table"` es lo que importa: el filtro es a nivel de tabla, no de
    columna, así que también bloquea cualquier diferencia de columnas o índices
    adentro de ellas.
    """
    if type_ == "table" and name in TABLAS_FUERA:
        return False
    return True


def run_migrations_offline() -> None:
    """Genera el SQL sin conectarse. Sirve para ver qué haría."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_object=incluir_objeto,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Se conecta y aplica."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # `compare_type=True`: compara los tipos de las columnas, no solo si
            # existen. Sin esto, cambiar `VARCHAR(30)` por `VARCHAR(60)` no se
            # detecta y la migración no se escribe.
            compare_type=True,
            compare_server_default=True,
            # El filtro que evita que proponga borrar las tablas de `config_*`.
            include_object=incluir_objeto,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()