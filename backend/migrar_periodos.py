"""Los PERÍODOS de un ejercicio contable: los 12 meses, que se abren y se cierran.

Hoy el sistema tiene el ejercicio (2026/2027) con un solo flag `cerrado`, y ese
flag solo se mira al CREAR un comprobante. No frena anular ni modificar: hoy se
puede anular tranquilamente un recibo de septiembre con el ejercicio abierto, que
es justo lo que el contador pidió que no pase.

Un período es **un mes del ejercicio**, no un mes del calendario: con el ejercicio
del 01/09/2026 al 31/08/2027, el período 1 es septiembre 2026 y el 12 es agosto
2027. Por eso se guardan las fechas de cada período en la fila y no se calculan
al vuelo: la consulta de "¿esta fecha cae en un período cerrado?" tiene que ser un
`WHERE fecha_inicio <= ? <= fecha_fin`, no una cuenta de meses.

Nacen los 12 ABIERTOS: el contador trabaja y va cerrando a medida que termina
cada mes. Si arrancaran cerrados no se podría cargar nada el primer día.

El script es idempotente: se puede correr N veces. No borra ni modifica datos.
"""

from datetime import date

from sqlalchemy import text

from app.database import engine

MESES = (
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
)


def ultimo_dia(anio: int, mes: int) -> int:
    """Cuántos días tiene ese mes. Sin `calendar`: no hace falta traerlo."""
    if mes == 12:
        return 31
    return (date(anio, mes + 1, 1) - date(anio, mes, 1)).days


def generar_periodos(conn, ejercicio_id: int, fecha_inicio: date) -> int:
    """Crea los 12 períodos del ejercicio, si no están.

    El mes 1 es el de `fecha_inicio`; el 12 es doce meses después. Si el ejercicio
    arranca a mitad de mes (raro, pero pasa), el período 1 empieza el día 1 de ese
    mes para no dejar días huérfanos fuera de todo período.
    """
    anio, mes = fecha_inicio.year, fecha_inicio.month
    nuevos = 0
    for numero in range(1, 13):
        existe = conn.execute(
            text("SELECT 1 FROM periodos WHERE id_ejercicio = :e AND numero = :n"),
            {"e": ejercicio_id, "n": numero},
        ).scalar()
        if existe:
            continue
        m = ((mes - 1 + numero - 1) % 12) + 1
        a = anio + (mes - 1 + numero - 1) // 12
        conn.execute(
            text(
                "INSERT INTO periodos "
                "(id_ejercicio, numero, nombre, fecha_inicio, fecha_fin, cerrado, creado) "
                "VALUES (:e, :n, :nom, :fi, :ff, 0, NOW())"
            ),
            {
                "e": ejercicio_id,
                "n": numero,
                "nom": f"{MESES[m - 1]} {a}",
                "fi": date(a, m, 1),
                "ff": date(a, m, ultimo_dia(a, m)),
            },
        )
        nuevos += 1
    return nuevos


with engine.begin() as conn:
    existe_tabla = conn.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.TABLES "
            "WHERE TABLE_NAME = 'periodos'"
        )
    ).scalar()

    if not existe_tabla:
        conn.execute(
            text(
                """
                CREATE TABLE periodos (
                  id_periodo    INT NOT NULL AUTO_INCREMENT,
                  id_ejercicio  INT NOT NULL,
                  numero        TINYINT NOT NULL,
                  nombre        VARCHAR(40) NOT NULL,
                  fecha_inicio  DATE NOT NULL,
                  fecha_fin     DATE NOT NULL,
                  cerrado       TINYINT(1) NOT NULL DEFAULT 0,
                  cerrado_por   INT NULL,
                  cerrado_el    DATETIME NULL,
                  creado        DATETIME NOT NULL,
                  actualizado   DATETIME NULL,
                  PRIMARY KEY (id_periodo),
                  UNIQUE KEY uq_periodo_ejercicio_numero (id_ejercicio, numero),
                  KEY ix_periodos_fecha (fecha_inicio, fecha_fin),
                  KEY ix_periodos_ejercicio (id_ejercicio),
                  CONSTRAINT fk_periodo_ejercicio FOREIGN KEY (id_ejercicio)
                    REFERENCES ejercicios (id_ejercicio)
                    ON DELETE RESTRICT ON UPDATE CASCADE,
                  CONSTRAINT fk_periodo_cerrado_por FOREIGN KEY (cerrado_por)
                    REFERENCES usuarios (id)
                    ON DELETE SET NULL ON UPDATE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
        )
        print("+ tabla periodos")
    else:
        print("= tabla periodos ya existe")

        # La tabla se creó la primera vez SIN `cerrado_por` ni `cerrado_el`
        # (se agregaron después, cuando se decidió registrar quién cierra cada
        # período). Agregarlas acá para que una base vieja quede igual que una
        # nueva. Solo AGREGA columnas: no borra ni modifica nada.
        columnas = {
            row[0]
            for row in conn.execute(
                text(
                    "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                    "WHERE TABLE_NAME = 'periodos'"
                )
            ).all()
        }
        if "cerrado_por" not in columnas:
            conn.execute(text("ALTER TABLE periodos ADD COLUMN cerrado_por INT NULL"))
            print("+ columna periodos.cerrado_por")
        if "cerrado_el" not in columnas:
            conn.execute(text("ALTER TABLE periodos ADD COLUMN cerrado_el DATETIME NULL"))
            print("+ columna periodos.cerrado_el")
        if "cerrado_por" not in columnas:
            conn.execute(
                text(
                    "ALTER TABLE periodos ADD CONSTRAINT fk_periodo_cerrado_por "
                    "FOREIGN KEY (cerrado_por) REFERENCES usuarios (id) "
                    "ON DELETE SET NULL ON UPDATE CASCADE"
                )
            )
            print("+ fk periodos.cerrado_por -> usuarios.id")

    # Los períodos de los ejercicios que YA están cargados (no solo los nuevos).
    ejercicios = conn.execute(
        text("SELECT id_ejercicio, nombre, fecha_inicio FROM ejercicios")
    ).all()
    for eid, nombre, fecha_inicio in ejercicios:
        n = generar_periodos(conn, eid, fecha_inicio)
        print(f"{'+' if n else '='} ejercicio {nombre}: {n} períodos nuevos")

print()
print("períodos contables: listo")
