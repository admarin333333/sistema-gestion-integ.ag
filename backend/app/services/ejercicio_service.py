"""El ejercicio contable del ESTUDIO.

Un solo lugar que responde tres preguntas:

- ¿En qué ejercicio cae hoy? (`vigente`)
- ¿Se puede asentar en esta fecha? (`verificar_abierta`)
- ¿Qué ejercicio hay que filtrar en la pantalla de Asientos? (`el_de_la_fecha`)

Recordatorio que está en todos lados: esto es el ejercicio del estudio, no el
de cada cliente. El del cliente vive en `bal_rt54_ejercicios` y tiene otra fecha
de cierre.
"""

from datetime import date, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import Rechazo
from app.models.ejercicio import Ejercicio


def listar(db: Session) -> list[Ejercicio]:
    """Todos los ejercicios, del más nuevo al más viejo."""
    return list(
        db.execute(
            select(Ejercicio).order_by(
                Ejercicio.fecha_inicio.desc(), Ejercicio.id_ejercicio.desc()
            )
        )
        .scalars()
        .all()
    )


def obtener(db: Session, ejercicio_id: int) -> Ejercicio:
    ejercicio = db.get(Ejercicio, ejercicio_id)
    if ejercicio is None:
        raise Rechazo("No existe ese ejercicio", 404)
    return ejercicio


def el_de_la_fecha(db: Session, fecha: date) -> Ejercicio | None:
    """El ejercicio **abierto** que contiene esa fecha, o None."""
    return db.execute(
        select(Ejercicio)
        .where(
            Ejercicio.cerrado.is_(False),
            Ejercicio.fecha_inicio <= fecha,
            Ejercicio.fecha_fin >= fecha,
        )
        .order_by(Ejercicio.fecha_inicio.desc())
    ).scalars().first()


def vigente(db: Session, hoy: date | None = None) -> Ejercicio | None:
    """El ejercicio abierto que contiene hoy. El que está trabajando el estudio."""
    return el_de_la_fecha(db, hoy or date.today())


def verificar_abierta(db: Session, fecha: date) -> Ejercicio:
    """Para asentar en esa fecha tiene que haber un ejercicio abierto que la cubra.

    Se rechaza, y no se inventa el número, porque un comprobante guardado en el
    ejercicio equivocado después no se puede corregir sin romper la numeración.
    """
    ejercicio = el_de_la_fecha(db, fecha)
    if ejercicio is not None:
        return ejercicio

    # Se busca cuál es el problema para poder explicarlo bien: ¿no hay ningún
    # ejercicio, o es que esa fecha cae en uno ya cerrado?
    todos = listar(db)
    if not todos:
        raise Rechazo(
            "No hay ningún ejercicio configurado. Cargalo en Configuración → "
            "Ejercicio antes de asentar.",
            400,
        )
    cerrados = [e for e in todos if e.cerrado and e.fecha_inicio <= fecha <= e.fecha_fin]
    if cerrados:
        nombres = ", ".join(e.nombre for e in cerrados)
        raise Rechazo(
            f"La fecha {fecha.isoformat()} cae en el ejercicio «{nombres}», "
            "que está cerrado. Reabrilo o abrí el ejercicio siguiente.",
            400,
        )

    # Ninguno cubre la fecha: se dice cuál es el período habilitado.
    abiertos = [e for e in todos if not e.cerrado]
    if abiertos:
        detalle = "; ".join(
            f"{e.nombre}: {e.fecha_inicio.isoformat()} a {e.fecha_fin.isoformat()}"
            for e in abiertos
        )
    else:
        detalle = "no hay ninguno abierto"
    raise Rechazo(
        f"La fecha {fecha.isoformat()} está fuera de todo ejercicio "
        f"habilitado ({detalle}).",
        400,
    )


# ------------------------------------------------------------------- escrituras

def crear(
    db: Session,
    nombre: str,
    fecha_inicio: date,
    fecha_fin: date,
    cerrado: bool = False,
) -> Ejercicio:
    nombre = (nombre or "").strip()
    if not nombre:
        raise Rechazo("Poné un nombre para el ejercicio", 400)
    if fecha_fin < fecha_inicio:
        raise Rechazo(
            f"La fecha de fin ({fecha_fin.isoformat()}) es anterior a la de "
            f"inicio ({fecha_inicio.isoformat()})",
            400,
        )

    if db.execute(
        select(Ejercicio).where(Ejercicio.nombre == nombre)
    ).scalars().first():
        raise Rechazo(f"Ya existe un ejercicio llamado «{nombre}»", 409)

    # Dos ejercicios abiertos que se pisan dejarían la numeración ambigua: la
    # fecha caería en dos a la vez. Se avisa antes de guardar.
    nuevo = Ejercicio(
        nombre=nombre,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        cerrado=cerrado,
    )
    if not cerrado:
        for otro in db.execute(select(Ejercicio)).scalars().all():
            if otro.cerrado:
                continue
            if otro.fecha_inicio <= fecha_fin and fecha_inicio <= otro.fecha_fin:
                raise Rechazo(
                    f"Se pisa con el ejercicio «{otro.nombre}» "
                    f"({otro.fecha_inicio.isoformat()} a "
                    f"{otro.fecha_fin.isoformat()}). Cerrá ese primero o corré "
                    "las fechas.",
                    409,
                )

    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)

    # El ejercicio nace con sus 12 períodos (los meses, del 1 al 12), TODOS
    # ABIERTOS: el contador trabaja y va cerrando a medida que termina cada mes.
    # Si arrancaran cerrados no se podría cargar nada el primer día.
    #
    # Se usa el import diferido porque `periodo_service` importa los modelos de
    # factura y recibo, que a su vez importan cosas de acá.
    from app.services import periodo_service

    periodo_service.generar(db, nuevo)

    return nuevo


def editar(
    db: Session, ejercicio_id: int, nombre: str, fecha_inicio: date, fecha_fin: date
) -> Ejercicio:
    """Cambiar el nombre o las fechas de un ejercicio.

    **Cerrar o abrir es aparte** (`cerrar` / `abrir`) porque es la decisión que
   bloquea la contabilidad y no debería pasar por un guardado de routine.
    """
    ejercicio = obtener(db, ejercicio_id)
    nombre = (nombre or "").strip()
    if not nombre:
        raise Rechazo("Poné un nombre para el ejercicio", 400)
    if fecha_fin < fecha_inicio:
        raise Rechazo(
            f"La fecha de fin ({fecha_fin.isoformat()}) es anterior a la de "
            f"inicio ({fecha_inicio.isoformat()})",
            400,
        )
    repetido = db.execute(
        select(Ejercicio).where(
            Ejercicio.nombre == nombre, Ejercicio.id_ejercicio != ejercicio_id
        )
    ).scalars().first()
    if repetido:
        raise Rechazo(f"Ya existe un ejercicio llamado «{nombre}»", 409)

    ejercicio.nombre = nombre
    ejercicio.fecha_inicio = fecha_inicio
    ejercicio.fecha_fin = fecha_fin
    ejercicio.actualizado = datetime.utcnow()
    db.commit()
    db.refresh(ejercicio)
    return ejercicio


def cambiar_estado(db: Session, ejercicio_id: int, cerrado: bool) -> Ejercicio:
    """Cerrar un ejercicio lo deja sin recibir asientos.

    No hace falta que esté todo conciliado para cerrarlo: es una trava para que
    nadie meta movimientos abajo de una fecha ya cerrada sin darse cuenta.
    """
    ejercicio = obtener(db, ejercicio_id)
    if ejercicio.cerrado == cerrado:
        return ejercicio

    if not cerrado:
        for otro in db.execute(select(Ejercicio)).scalars().all():
            if otro.id_ejercicio == ejercicio_id or otro.cerrado:
                continue
            if otro.fecha_inicio <= ejercicio.fecha_fin and ejercicio.fecha_inicio <= otro.fecha_fin:
                raise Rechazo(
                    f"No se puede abrir: se pisa con el ejercicio «{otro.nombre}»",
                    409,
                )

    ejercicio.cerrado = cerrado
    ejercicio.actualizado = datetime.utcnow()
    db.commit()
    db.refresh(ejercicio)
    return ejercicio


def resumen(db: Session) -> dict:
    """Lo que necesita la pantalla: el ejercicio abierto y cuántos hay."""
    abierto = vigente(db)
    total = db.execute(select(func.count(Ejercicio.id_ejercicio))).scalar() or 0
    cerrados = (
        db.execute(
            select(func.count(Ejercicio.id_ejercicio)).where(Ejercicio.cerrado.is_(True))
        ).scalar()
        or 0
    )
    return {
        "vigente": abierto,
        "cantidad": total,
        "cerrados": cerrados,
        "abiertos": total - cerrados,
    }


def a_json(e: Ejercicio) -> dict:
    return {
        "id_ejercicio": e.id_ejercicio,
        "nombre": e.nombre,
        "fecha_inicio": e.fecha_inicio,
        "fecha_fin": e.fecha_fin,
        "cerrado": e.cerrado,
        # Si hoy cae acá, es el que está trabajando el estudio.
        "es_el_de_hoy": (
            not e.cerrado and e.fecha_inicio <= date.today() <= e.fecha_fin
        ),
    }