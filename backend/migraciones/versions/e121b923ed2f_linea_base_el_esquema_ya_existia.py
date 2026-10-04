"""
linea base: el esquema (se crea entero, para bases nuevas)

QUÉ ES ESTA REVISIÓN

El punto de partida de Alembic. El esquema del estudio ya estaba armado por 23
scripts `migrar_*.py` sueltos antes de que hubiera Alembic, así que hay dos cosas
que resolver:

1. **La base que YA EXISTE** (la del estudio): se marca con `alembic stamp head`,
   que solo escribe una fila en `alembic_version`. No se toca ni una tabla.

2. **Una base NUEVA, desde cero**: se arma con `alembic upgrade head`, que corre
   esta revisión y **crea todas las tablas** a partir de los modelos.

POR QUÉ `create_all` Y NO UNA LISTA DE OPERACIONES

Lo normal en Alembic es que cada migración escriba las operaciones una por una
(`op.create_table(...)`, `op.add_column(...)`). Esta NO lo hace, y a propósito:

Si esta revisión(listara las 43 tablas a mano, habría que escribir 43
`create_table` con cada columna, y **esa lista se desactualiza sola**: el día que
se agrega una columna a un modelo, alguien tiene que acordarse deEditing también
esta revisión vieja, y si no se olvida, una base nueva nace con el esquema
incompleto y falla recién cuando el sistema la usa.

Con `create_all` pasa lo contrario: la revisión dice "el esquema es el que dicen
los modelos", y los modelos son la única fuente de verdad. Se agrega una columna
al modelo, corrés el autogen (que genera una migración NUEVA para la base
existente), y la base nueva la va a tener sola cuando corra esta.

CUANDO NO HACE NADA

Si la base ya tiene las tablas —la del estudio, o una de pruebas que se armó
antes—, `create_all` no hace nada: `CREATE TABLE` sobre una tabla que existe da
error, y SQLAlchemy lo evita por lo mismo. Por eso esta migración es segura de
correr sobre cualquier base.

Y si la base ya está marcada con `stamp`, esta revisión ni siquiera se ejecuta:
Alembic ya está en `head`.

DESPUÉS DE ESTA

Todo cambio de esquema va por Alembic:

    alembic revision --autogenerate -m "lo que se agregó"
    alembic upgrade head

Los `migrar_*.py` **no se borran**: los que cargan DATOS (el ejercicio, los 12
períodos, el plan de cuentas, las alícuotas) siguen haciendo falta, porque los
datos iniciales no son esquema. Lo que cambia es que el ESQUEMA ya no se toca
con scripts sueltos.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e121b923ed2f"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _metadata():
    """
    Trae `Base.metadata` con TODOS los modelos cargados.

    Importar `app.models` (el paquete entero) es lo que hace que las tablas se
    registran: un modelo que no se importa no existe para el ORM, y
    `create_all` se saltearía su tabla sin avisar.

    El import va acá adentro y no arriba del archivo a propósito: en el momento de
    correr la migración, no cuando se lee el módulo.
    """
    from app import models  # noqa: F401
    from app.database import Base

    return Base.metadata


def upgrade() -> None:
    """Crea el esquema completo. No hace nada si las tablas ya existen."""
    _metadata().create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    """
    Borra el esquema completo.

    Es una bomba con Responsibilities: `drop_all` no pregunta y borra TODO. Por
    eso el downgrade no lo usa: para volver atrás de esta revisión, la forma
    segura es borrar la base y volver a armarla.

    Con `alembic downgrade base` lo que se quiere decir casi siempre es "tirá
    todo y empezamos de cero", y eso se hace mejor por fuera, con un DROP DATABASE
    que se ve.
    """
    raise NotImplementedError(
        "Esta revisión es la línea base: no se puede volver atrás con Alembic.\n"
        "\n"
        "Borrar el esquema entero desde acá es peligroso porque `drop_all` no "
        "pregunta y borra TODAS las tablas, datos incluidos.\n"
        "\n"
        "Si lo que querés es empezar de cero, borrá la base a mano y volvé a "
        "armarla:\n"
        "    DROP DATABASE gestion_contable;\n"
        "    CREATE DATABASE gestion_contable CHARACTER SET utf8mb4;\n"
        "    alembic upgrade head\n"
    )