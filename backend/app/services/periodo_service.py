"""Los PERÍODOS contables: los 12 meses de un ejercicio, que se abren y cierran.

Un solo lugar responde cuatro preguntas:

  - ¿En qué período cae hoy? (`de_hoy`)
  - ¿En qué período cae ESTA fecha? (`de_la_fecha`)
  - ¿Se puede escribir en esta fecha? (`verificar_abierto`)
  - ¿Qué períodos tiene este ejercicio y qué hay en cada uno? (`listar`)

**Por qué existe el módulo si ya está el ejercicio.** El ejercicio tiene un solo
`cerrado` y ese flag solo se mira al crear un comprobante: hoy se puede anular o
modificar un recibo de septiembre con el ejercicio abierto, y no hay forma de
decirle al sistema "septiembre ya está, no lo toques más". Con los períodos, esa
trava existe y el contador la maneja mes a mes.

**Cerrar NO bloquea leer.** Se sigue consulting el Mayor, los informes y los
listados. Cerrado es "no escribas acá", no "no mires acá".

**Y no reemplaza al ejercicio.** Son dos niveles: el ejercicio cerrado dice "nadie
escribe en este año"; el período cerrado dice "nadie escribe en este mes". Abrir
un período de un ejercicio cerrado tiene que seguir rebotando, y por eso
`verificar_abierto` consulta las dos cosas.
"""

from datetime import date, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import Rechazo
from app.models.asiento import Asiento
from app.models.ejercicio import Ejercicio
from app.models.factura import Factura
from app.models.periodo import Periodo
from app.models.recibo import Recibo

MESES = (
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
)


# ------------------------------------------------------------------- lectura


def listar(db: Session, ejercicio_id: int) -> list[Periodo]:
    """Los 12 períodos de un ejercicio, del 1 al 12."""
    return list(
        db.execute(
            select(Periodo)
            .where(Periodo.id_ejercicio == ejercicio_id)
            .order_by(Periodo.numero)
        )
        .scalars()
        .all()
    )


def de_la_fecha(db: Session, fecha: date) -> Periodo | None:
    """El período que contiene esa fecha, esté abierto o cerrado.

    No filtra por `cerrado` a propósito: para MOSTRAR hay que saber también en
    qué período cerrado cae la fecha (si no, el error no puede decir "el período
    de septiembre está cerrado", que es la mitad del mensaje útil).
    """
    return db.execute(
        select(Periodo)
        .where(Periodo.fecha_inicio <= fecha, Periodo.fecha_fin >= fecha)
        .order_by(Periodo.id_periodo.desc())
    ).scalars().first()


def de_hoy(db: Session, hoy: date | None = None) -> Periodo | None:
    """El período que contiene hoy: en el que el contador está trabajando."""
    return de_la_fecha(db, hoy or date.today())


def obtener(db: Session, periodo_id: int) -> Periodo:
    p = db.get(Periodo, periodo_id)
    if p is None:
        raise Rechazo("No existe ese período", 404)
    return p


# ------------------------------------------------------------------- la trava


def verificar_abierto(
    db: Session, fecha: date, que: str = "trabajar en esa fecha"
) -> Periodo | None:
    """Si la fecha cae en un período cerrado, no se deja seguir.

    `que` es lo que el contador estaba tratando de hacer ("anular ese recibo",
    "cargar una factura") y va en el mensaje: *"No se puede anular ese recibo: el
    período de Septiembre 2026 está cerrado"* dice mucho más que *"Período
    cerrado"*.

    Se consulta el ejercicio también, porque un período de un ejercicio cerrado
    tiene que seguir rebotando: abrir el mes no habilita un año cerrado.

    Si no hay períodos cargados (base vieja, o un ejercicio creado antes de la
    migración) NO bloquea: es preferible dejar pasar a que el sistema se trabe
    entero. El caso se cubre en `tests`.
    """
    hay_periodos = db.execute(select(func.count(Periodo.id_periodo))).scalar() or 0
    if not hay_periodos:
        return None

    periodo = de_la_fecha(db, fecha)
    if periodo is None:
        # La fecha cae fuera de todo período. Puede ser un ejercicio viejo sin
        # períodos: se deja pasar y lo dice el ejercicio cerrado, si lo está.
        _verificar_ejercicio(db, fecha)
        return None

    if periodo.cerrado:
        raise Rechazo(
            f"No se puede {que}: el período {periodo.numero} · "
            f"{periodo.nombre} ({periodo.fecha_inicio.isoformat()} a "
            f"{periodo.fecha_fin.isoformat()}) está cerrado. "
            "Reabrilo desde Configuración → Períodos si te equivocaste.",
            409,
        )

    _verificar_ejercicio(db, fecha)
    return periodo


def _verificar_ejercicio(db: Session, fecha: date) -> None:
    """El ejercicio cerrado manda sobre el período: es el nivel más arriba.

    El mensaje de `ejercicio_service` se deja tal cual: ya dice qué ejercicio
    es, que está cerrado y cómo abrirlo. Agregarle algo lo confunde más de lo
    que ayuda.

    Solo se le cambia el código de error a **409**: "no se puede trabajar en
    esta fecha" — esté cerrado el ejercicio, el mes, o la fecha caiga fuera de
    todo — es la misma cosa para el contador y para la pantalla. Antes el
    mensaje de ejercicio cerrado era 400 (dato mal cargado) y el de período
    cerrado 409 (conflicto), y eso obligaba al frontend a tratar dos casos que
    en la pantalla son idénticos.
    """
    from app.services import ejercicio_service

    try:
        ejercicio_service.verificar_abierta(db, fecha)
    except Rechazo as e:
        raise Rechazo(str(e), 409) from e


def verificar_ejercicio(db: Session, fecha: date) -> None:
    """Solo el ejercicio, sin mirar el período. Para crear un comprobante."""
    _verificar_ejercicio(db, fecha)


# ------------------------------------------------------------------- escrituras


MESES_POR_NUMERO = MESES


def ultimo_dia_de(anio: int, mes: int) -> int:
    """Cuántos días tiene ese mes."""
    if mes == 12:
        return 31
    return (date(anio, mes + 1, 1) - date(anio, mes, 1)).days


def generar(db: Session, ejercicio) -> int:
    """Crea los 12 períodos de un ejercicio si no están. Devuelve cuántos creó.

    El mes 1 es el de `ejercicio.fecha_inicio`; el 12 es doce meses después.
    Todos ABIERTOS.

    Vive acá y no en la migración para que un ejercicio nuevo creado desde la
    pantalla nazca con sus períodos, sin que nadie tenga que acordarse de correr
    un script. La migración llama a la misma lógica.
    """
    anio, mes = ejercicio.fecha_inicio.year, ejercicio.fecha_inicio.month
    existentes = {
        p.numero
        for p in db.execute(
            select(Periodo).where(Periodo.id_ejercicio == ejercicio.id_ejercicio)
        ).scalars().all()
    }

    nuevos = []
    for numero in range(1, 13):
        if numero in existentes:
            continue
        m = ((mes - 1 + numero - 1) % 12) + 1
        a = anio + (mes - 1 + numero - 1) // 12
        nuevos.append(
            Periodo(
                id_ejercicio=ejercicio.id_ejercicio,
                numero=numero,
                nombre=f"{MESES[m - 1]} {a}",
                fecha_inicio=date(a, m, 1),
                fecha_fin=date(a, m, ultimo_dia_de(a, m)),
                cerrado=False,
            )
        )
    if nuevos:
        db.add_all(nuevos)
        db.commit()
    return len(nuevos)


def cambiar_estado(
    db: Session,
    periodo_id: int,
    cerrado: bool,
    usuario_id: int | None = None,
    forzar: bool = False,
) -> Periodo:
    """Abrir o cerrar un período.

    **Cerrar un período con documentos adentro se puede**, pero avisando cuántos
    hay. El cierre es una trava para no escribir por error, no una validación
    contable: si el contador quiere cerrar septiembre con lo que hay, se cierra.
    Lo que no se puede es cerrar sin querer, y por eso `forzar` obliga a que la
    pantalla haya mostrado el número primero.
    """
    periodo = obtener(db, periodo_id)
    if periodo.cerrado == cerrado:
        return periodo

    if not cerrado:
        ejercicio = db.get(Ejercicio, periodo.id_ejercicio)
        if ejercicio is not None and ejercicio.cerrado:
            raise Rechazo(
                f"No se puede abrir el período {periodo.numero} · "
                f"{periodo.nombre}: el ejercicio «{ejercicio.nombre}» está "
                "cerrado. Reabrí el ejercicio primero.",
                409,
            )

    if cerrado:
        n_docs, n_asientos = conteo(db, periodo)
        if (n_docs or n_asientos) and not forzar:
            raise Rechazo(
                f"El período {periodo.numero} · {periodo.nombre} tiene "
                f"{n_docs} documento(s) y {n_asientos} asiento(s) cargados. "
                "Si lo cerrás igual no vas a poder anularlos ni modificarlos. "
                "Volvé a intentarlo confirmando.",
                409,
            )
        periodo.cerrado_por = usuario_id
        periodo.cerrado_el = datetime.utcnow()
    else:
        periodo.cerrado_por = None
        periodo.cerrado_el = None

    periodo.cerrado = cerrado
    periodo.actualizado = datetime.utcnow()
    db.commit()
    db.refresh(periodo)
    return periodo


def conteo(db: Session, periodo: Periodo) -> tuple[int, int]:
    """Cuántos documentos y cuántos asientos hay con fecha en el período.

    Se cuenta por `fecha`, no por `id`: es lo que decide a qué período pertenece
    cada cosa. Solo lo que está **contabilizado** cuenta como asiento: un
    borrador no llegó al libro.
    """
    cond = [
        Factura.fecha >= periodo.fecha_inicio,
        Factura.fecha <= periodo.fecha_fin,
        Factura.estado != "anulada",
    ]
    documentos = (
        db.execute(select(func.count(Factura.id)).where(*cond)).scalar() or 0
    )
    documentos += (
        db.execute(
            select(func.count(Recibo.id)).where(
                Recibo.fecha >= periodo.fecha_inicio,
                Recibo.fecha <= periodo.fecha_fin,
                Recibo.estado != "anulado",
            )
        ).scalar()
        or 0
    )

    asientos = (
        db.execute(
            select(func.count(Asiento.id_asiento)).where(
                Asiento.estado == "CONTABILIZADO",
                Asiento.fecha >= periodo.fecha_inicio,
                Asiento.fecha <= periodo.fecha_fin,
            )
        ).scalar()
        or 0
    )
    return documentos, asientos


# ------------------------------------------------------------------- json


def a_json(p: Periodo, db: Session | None = None) -> dict:
    datos = {
        "id_periodo": p.id_periodo,
        "id_ejercicio": p.id_ejercicio,
        "numero": p.numero,
        "nombre": p.nombre,
        "fecha_inicio": p.fecha_inicio,
        "fecha_fin": p.fecha_fin,
        "cerrado": p.cerrado,
        "cerrado_el": p.cerrado_el,
    }
    if db is not None:
        documentos, asientos = conteo(db, p)
        datos["documentos"] = documentos
        datos["asientos"] = asientos
        datos["tiene_movimientos"] = bool(documentos or asientos)
    return datos
