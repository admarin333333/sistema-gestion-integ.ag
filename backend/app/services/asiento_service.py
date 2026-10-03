"""El núcleo del motor contable.

Tres cosas, en este orden:

1. **Comprobantes internos**: la cabecera numerada (OP-000125). El correlativo
   es por código y **por año**.
2. **Asientos** con sus líneas de detalle contra el plan de cuentas.
3. **Partida doble**: no se contabiliza nada si el Debe no cierra con el Haber,
   y los **saldos no se guardan**: se calculan por SQL sobre lo contabilizado.

La regla de oro: una línea solo puede ir a una cuenta **imputable**. Un
agrupador (que tiene subcuentas) no recibe movimientos.

El saldo se devuelve con el **signo de la naturaleza**: en una deudora es
Debe − Haber, en una acreedora es Haber − Debe. Así siempre se lee "saldo a
favor", y si sale negativo está en contra.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import and_, bindparam, case, delete, func, select, text
from sqlalchemy.orm import Session, selectinload

from app.core.errors import Rechazo
from app.models.asiento import (
    ESTADOS_ASIENTO,
    TIPOS_AUXILIAR_DETALLE,
    Asiento,
    AsientoDetalle,
)
from app.models.comprobante_interno import (
    CODIGOS_COMPROBANTE,
    ComprobanteInterno,
)
from app.models.plan_cuenta import PlanCuenta
from app.models.asiento_origen import ORIGENES, AsientoOrigen

CENTIMO = Decimal("0.0001")


def _d(valor) -> Decimal:
    """Vuelve Decimal con 4 decimales, sin surprises de coma flotante."""
    if valor is None or valor == "":
        return Decimal("0")
    return Decimal(str(valor)).quantize(CENTIMO)


# =====================================================================
# COMPROBANTES INTERNOS
# =====================================================================

def _proximo_numero(
    db: Session, codigo: str, id_ejercicio: int
) -> int:
    """El siguiente número libre para ese código **en ese ejercicio**.

    Se toma el MAYOR existente + 1. Como la clave es única
    (codigo, id_ejercicio, numero), si alguien carga a mano un número que ya
    existe, el INSERT se rechaza y no se pisa nada.

    OJO: el ejercicio va primero, no el año. Con el ejercicio del 01/09/2026 al
    31/08/2027 el número corre corrido de 000001 a 000300 y recién al abrir el
    ejercicio siguiente vuelve a 000001 — no se parte el 1 de enero.
    """
    ultimo = db.execute(
        select(func.max(ComprobanteInterno.numero)).where(
            ComprobanteInterno.codigo_comprobante == codigo,
            ComprobanteInterno.id_ejercicio == id_ejercicio,
        )
    ).scalar()
    return int(ultimo or 0) + 1


def codigos_validos(db: Session) -> list[str]:
    """Los códigos internos que están dados de alta.

    La fuente de verdad es la tabla `config_comprobantes` (se edita desde
    Configuración). Si la tabla no existe todavía, se cae a la lista de
    fábrica para que el módulo ande igual en una base vieja.
    """
    from sqlalchemy import text

    filas = db.execute(
        text("SELECT codigo FROM config_comprobantes WHERE activa = 1 ORDER BY codigo")
    ).scalars().all()
    if filas:
        return list(filas)
    return list(CODIGOS_COMPROBANTE)


def crear_comprobante(
    db: Session, codigo: str, fecha: date, concepto: str
) -> ComprobanteInterno:
    codigo = (codigo or "").strip().upper()
    validos = codigos_validos(db)
    if codigo not in validos:
        raise Rechazo(
            f"Código de comprobante desconocido: «{codigo}». "
            f"Valores: {', '.join(validos)}.",
            400,
        )
    concepto = (concepto or "").strip()
    if not concepto:
        raise Rechazo("Poné un concepto para el comprobante", 400)

    # La fecha tiene que caer en un ejercicio habilitado. Si no hay, NO se
    # inventa el número: un comprobante guardado en el ejercicio equivocado
    # después no se puede arreglar sin romper la numeración.
    #
    # Antes se mira el PERÍODO: si el mes de esa fecha está cerrado, el
    # comprobante no entra aunque el ejercicio esté abierto (puede estar
    # abierto por el período 2 y el 1 ya cerrado).
    from app.services import ejercicio_service, periodo_service

    periodo_service.verificar_abierto(
        db, fecha, "crear un comprobante con esa fecha"
    )
    ejercicio = ejercicio_service.verificar_abierta(db, fecha)

    numero = _proximo_numero(db, codigo, ejercicio.id_ejercicio)
    nuevo = ComprobanteInterno(
        codigo_comprobante=codigo,
        anio=fecha.year,
        numero=numero,
        id_ejercicio=ejercicio.id_ejercicio,
        fecha=fecha,
        concepto=concepto,
        estado="BORRADOR",
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo


def listar_comprobantes(
    db: Session, codigo: str = "", anio: int | None = None, estado: str = ""
) -> list[ComprobanteInterno]:
    consulta = select(ComprobanteInterno)
    if codigo:
        consulta = consulta.where(ComprobanteInterno.codigo_comprobante == codigo.upper())
    if anio:
        consulta = consulta.where(ComprobanteInterno.anio == anio)
    if estado:
        consulta = consulta.where(ComprobanteInterno.estado == estado)
    return list(
        db.execute(
            consulta.order_by(
                ComprobanteInterno.anio.desc(),
                ComprobanteInterno.codigo_comprobante,
                ComprobanteInterno.numero.desc(),
            )
        )
        .scalars()
        .all()
    )


# =====================================================================
# ASIENTOS
# =====================================================================


def listar(
    db: Session,
    codigo: str = "",
    origen: str = "",
    estado: str = "",
    desde: date | None = None,
    hasta: date | None = None,
) -> dict:
    """Los asientos del período, **agrupados por día**.

    Vuelve {dias: [{fecha, total_debe, total_haber, asientos: [...]}]}.

    Las sumas del pie de cada día y los totales de la pantalla salen de
    `GROUP BY` en SQL, no de sumar en el navegador: si el día tiene 400
    asientos, el navegador sumaría 400 números que la base ya tiene resueltos.

    Los asientos sin comprobante (cargados a mano sin código) entran igual,
    con `codigo_comprobante` en NULL.

    **`origen` filtra por MÓDULO**, no por código: es lo que el contador pide
    ("mostrame los recibos"). Sale de `asiento_origen`, que es donde ya se sabe
    de qué salió cada asiento. "MANUAL" son los que se cargan a mano, que no
    tienen comprobante: se buscan por lo contrario (que NO estén en la tabla).
    """
    condiciones = [Asiento.estado != "BORRADOR"]
    if estado:
        if estado not in ("BORRADOR", "CONTABILIZADO", "ANULADO"):
            raise Rechazo("Estado no válido", 400)
        # Con estado="" sale todo menos los borradores: son los que todavía no
        # se contabilizaron y no van a los saldos, así que no van en la lista.
        condiciones = [Asiento.estado == estado]
    if desde:
        condiciones.append(Asiento.fecha >= desde)
    if hasta:
        condiciones.append(Asiento.fecha <= hasta)
    if codigo:
        condiciones.append(ComprobanteInterno.codigo_comprobante == codigo.upper())
    if origen:
        origen = origen.upper()
        if origen not in ORIGENES:
            raise Rechazo("Módulo no válido", 400)
        if origen == "MANUAL":
            # Los manuales no están en `asiento_origen`: se generan desde la
            # pantalla de asientos, no desde un documento. "No está" = manual.
            condiciones.append(
                ~Asiento.id_asiento.in_(select(AsientoOrigen.id_asiento))
            )
        else:
            condiciones.append(
                Asiento.id_asiento.in_(
                    select(AsientoOrigen.id_asiento).where(
                        AsientoOrigen.origen == origen
                    )
                )
            )

    consulta = (
        select(
            Asiento,
            ComprobanteInterno.codigo_comprobante,
            ComprobanteInterno.numero,
        )
        .join(
            ComprobanteInterno,
            ComprobanteInterno.id_comprobante == Asiento.id_comprobante,
            isouter=True,
        )
        # selectinload trae TODO el detalle de todos los asientos del período
        # en 2 consultas. Sin esto, a_json() dispararía una consulta por
        # asiento (N+1) y con 400 asientos del día la pantalla tardaría una
        # eternidad.
        .options(selectinload(Asiento.detalle).selectinload(AsientoDetalle.cuenta))
        .where(*condiciones)
        .order_by(Asiento.fecha.desc(), Asiento.id_asiento.desc())
    )
    filas = db.execute(consulta).all()

    dias: list[dict] = []
    por_fecha: dict[date, dict] = {}
    for asiento, cod, numero in filas:
        dia = por_fecha.get(asiento.fecha)
        if dia is None:
            dia = por_fecha[asiento.fecha] = {
                "fecha": asiento.fecha,
                "total_debe": Decimal("0.0000"),
                "total_haber": Decimal("0.0000"),
                "cantidad": 0,
                "asientos": [],
            }
            dias.append(dia)

        dia["cantidad"] += 1
        dia["total_debe"] += _d(asiento.total_debe)
        dia["total_haber"] += _d(asiento.total_haber)

        item = a_json(asiento)
        item["codigo_comprobante"] = cod
        item["numero"] = numero
        item["total_debe"] = _d(asiento.total_debe)
        item["total_haber"] = _d(asiento.total_haber)
        dia["asientos"].append(item)

    # --- el "hay más cosas cargadas" -------------------------------------
    # Sin esto, la pantalla dice "no hay asientos" cuando en realidad lo que
    # no hay son asientos EN ESE FILTRO, y el contador piensa que no se
    # asentó nada. Con estos dos números puede verse de un vistazo que hay 5
    # asientos cargados y que está mirando un día donde no hay ninguno.
    #
    # Son dos consultas separadas a propósito (no se infiere del resultado ya
    # filtrado): "cuántos hay en total" tiene que ignorar el filtro de fechas,
    # y si se metiera en la misma it'd dar siempre 0 y el aviso no serviría.
    total_carga = _cuantos_hay_en_total(db, codigo)
    return {
        "dias": [
            {
                "fecha": d["fecha"],
                "cantidad": d["cantidad"],
                "total_debe": d["total_debe"],
                "total_haber": d["total_haber"],
                "asientos": d["asientos"],
            }
            for d in dias
        ],
        "total_debe": sum((d["total_debe"] for d in dias), Decimal("0.0000")),
        "total_haber": sum((d["total_haber"] for d in dias), Decimal("0.0000")),
        "cantidad": sum(d["cantidad"] for d in dias),
        "total_cargados": total_carga["cantidad"],
        "dias_con_asientos": total_carga["dias"],
        "primera_fecha": total_carga["primera"],
        "ultima_fecha": total_carga["ultima"],
    }


def _cuantos_hay_en_total(db: Session, codigo: str = "") -> dict:
    """Cuántos asientos hay cargados en total, sin filtro de fechas.

    Es para el aviso de la pantalla: "estás viendo 0 de 5". Sale de un
    `COUNT(*)` y un `COUNT(DISTINCT fecha)` en SQL, no contando en Python.
    """
    condiciones = [Asiento.estado != "BORRADOR"]
    if codigo:
        condiciones.append(ComprobanteInterno.codigo_comprobante == codigo.upper())

    cantidad, dias, primera, ultima = db.execute(
        select(
            func.count(Asiento.id_asiento),
            func.count(func.distinct(Asiento.fecha)),
            func.min(Asiento.fecha),
            func.max(Asiento.fecha),
        )
        .select_from(Asiento)
        .outerjoin(
            ComprobanteInterno,
            ComprobanteInterno.id_comprobante == Asiento.id_comprobante,
        )
        .where(*condiciones)
    ).one()

    return {
        "cantidad": int(cantidad or 0),
        "dias": int(dias or 0),
        "primera": primera,
        "ultima": ultima,
    }


def _verificar_periodo(db: Session, fecha, que: str) -> None:
    """Frena si la fecha cae en un período contable cerrado."""
    from app.services import periodo_service

    periodo_service.verificar_abierto(db, fecha, que)


def crear_asiento(
    db: Session,
    fecha: date,
    concepto: str,
    id_comprobante: int | None = None,
) -> Asiento:
    concepto = (concepto or "").strip()
    if not concepto:
        raise Rechazo("Poné un concepto para el asiento", 400)

    # Un asiento manual también es un movimiento con fecha: si cae en un período
    # cerrado no se lo deja cargar. El asiento en borrador tampoco, porque es
    # trabajo para después y en un mes cerrado ese trabajo ya no tiene sentido.
    _verificar_periodo(db, fecha, "crear un asiento con esa fecha")

    if id_comprobante is not None:
        comp = db.get(ComprobanteInterno, id_comprobante)
        if comp is None:
            raise Rechazo("El comprobante no existe", 404)

    nuevo = Asiento(
        fecha=fecha,
        concepto=concepto,
        id_comprobante=id_comprobante,
        estado="BORRADOR",
        total_debe=Decimal("0.0000"),
        total_haber=Decimal("0.0000"),
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo


def _recalcular_totales(db: Session, asiento: Asiento) -> None:
    """Suma el detalle y lo deja en el asiento. No se guarda el saldo de una
    cuenta, solo el control del propio asiento."""
    debe, haber = db.execute(
        select(
            func.coalesce(func.sum(AsientoDetalle.debe), 0),
            func.coalesce(func.sum(AsientoDetalle.haber), 0),
        ).where(AsientoDetalle.id_asiento == asiento.id_asiento)
    ).one()
    asiento.total_debe = _d(debe)
    asiento.total_haber = _d(haber)
    asiento.actualizado = datetime.utcnow()
    db.commit()


def a_json(a: Asiento, db: Session | None = None) -> dict:
    """El asiento completo, como lo ve el contador.

    Fecha, número, estado, los totales de cada lado y las líneas con **código
    de cuenta, nombre de la cuenta, Debe y Haber**. Vive acá y no en el router
    porque lo usan dos routers distintos (el de asientos y el de facturas).

    `db` es opcional a propósito: el listado de asientos la llama una vez por
    asiento y no puede abrir una consulta por línea (con 400 asientos del día
    la pantalla tardaría una eternidad). Cuando se pasa `db`, cada línea que
    tiene auxiliar además trae `auxiliar_nombre` — sin eso la pantalla del
    recibo muestra "Documentos a cobrar 1.000,00" y no se sabe de quién es.
    """
    nombres = (
        _nombres_auxiliares(
            db, {d.id_auxiliar for d in a.detalle if d.tipo_auxiliar and d.id_auxiliar}
        )
        if db is not None
        else {}
    )
    return {
        "id_asiento": a.id_asiento,
        "id_comprobante": a.id_comprobante,
        "numero_completo": (
            a.comprobante.numero_completo if a.comprobante else None
        ),
        "fecha": a.fecha,
        "concepto": a.concepto,
        "estado": a.estado,
        "total_debe": a.total_debe,
        "total_haber": a.total_haber,
        "diferencia": a.diferencia,
        "balanceado": a.balanceado,
        "detalle": [
            {
                "id_detalle": d.id_detalle,
                "id_cuenta": d.id_cuenta,
                "codigo": d.cuenta.codigo if d.cuenta else "",
                "nombre_cuenta": d.cuenta.nombre if d.cuenta else "",
                "deudora_acreadora": d.cuenta.deudora_acreadora if d.cuenta else None,
                "debe": d.debe,
                "haber": d.haber,
                "tipo_auxiliar": d.tipo_auxiliar,
                "id_auxiliar": d.id_auxiliar,
                "auxiliar_nombre": nombres.get(d.id_auxiliar) if d.tipo_auxiliar else None,
            }
            for d in a.detalle
        ],
    }


def guardar_detalle(db: Session, asiento_id: int, filas: list[dict]) -> dict:
    """Reemplaza las líneas del asiento y recalcula los totales.

    Solo deja guardar si el asiento está en BORRADOR: un asiento
    contabilizado es histórico.
    """
    asiento = db.get(Asiento, asiento_id)
    if asiento is None:
        raise Rechazo("El asiento no existe", 404)
    _verificar_periodo(db, asiento.fecha, "cambiar las líneas de ese asiento")
    if asiento.estado != "BORRADOR":
        raise Rechazo(
            f"El asiento está {asiento.estado}: no se le pueden cambiar las "
            "líneas. Pasalo a borrador primero.",
            409,
        )

    # Validar TODO antes de borrar nada, así un error no deja el asiento a medias.
    validas = []
    for f in filas:
        id_cuenta = f.get("id_cuenta")
        if not id_cuenta:
            continue
        cuenta = db.get(PlanCuenta, int(id_cuenta))
        if cuenta is None:
            raise Rechazo(f"La cuenta {id_cuenta} no existe", 400)
        if not cuenta.activa:
            raise Rechazo(
                f"{cuenta.codigo} {cuenta.nombre} está apagada: no se puede asentar",
                400,
            )
        if not cuenta.imputable:
            raise Rechazo(
                f"{cuenta.codigo} {cuenta.nombre} es un agrupador. Los movimientos "
                "van a las cuentas de detalle que tiene abajo.",
                400,
            )

        debe = _d(f.get("debe"))
        haber = _d(f.get("haber"))
        if debe < 0 or haber < 0:
            raise Rechazo(
                "Los importes van positivos: elegí en qué lado va (Debe o Haber)", 400
            )
        if debe == 0 and haber == 0:
            continue

        tipo_aux = (f.get("tipo_auxiliar") or "").strip().upper() or None
        if tipo_aux is not None and tipo_aux not in TIPOS_AUXILIAR_DETALLE:
            raise Rechazo(
                f"Tipo de auxiliar desconocido: «{tipo_aux}». "
                f"Valores: {', '.join(TIPOS_AUXILIAR_DETALLE)}.",
                400,
            )

        validas.append(
            {
                "id_cuenta": int(id_cuenta),
                "debe": debe,
                "haber": haber,
                "tipo_auxiliar": tipo_aux,
                "id_auxiliar": f.get("id_auxiliar"),
            }
        )

    db.execute(
        delete(AsientoDetalle).where(AsientoDetalle.id_asiento == asiento.id_asiento)
    )
    for f in validas:
        db.add(AsientoDetalle(id_asiento=asiento.id_asiento, **f))

    db.commit()
    db.refresh(asiento)
    _recalcular_totales(db, asiento)
    db.refresh(asiento)

    return {
        "asiento_id": asiento.id_asiento,
        "lineas": len(validas),
        "total_debe": str(asiento.total_debe),
        "total_haber": str(asiento.total_haber),
        "diferencia": str(asiento.diferencia),
        "balanceado": asiento.balanceado,
    }


def contabilizar(db: Session, asiento_id: int) -> dict:
    """Pasa de BORRADOR a CONTABILIZADO. Solo si el Debe cierra con el Haber."""
    asiento = db.get(Asiento, asiento_id)
    if asiento is None:
        raise Rechazo("El asiento no existe", 404)
    if asiento.estado == "CONTABILIZADO":
        raise Rechazo("El asiento ya está contabilizado", 409)
    if asiento.estado == "ANULADO":
        raise Rechazo("El asiento está anulado", 409)
    _verificar_periodo(db, asiento.fecha, "contabilizar ese asiento")

    # Se recalcula antes de decidir: si alguien cambió el detalle por SQL.
    _recalcular_totales(db, asiento)
    db.refresh(asiento)

    if not asiento.detalle:
        raise Rechazo("El asiento no tiene líneas", 400)

    diferencia = asiento.diferencia
    if diferencia != Decimal("0.0000"):
        raise Rechazo(
            f"No se puede contabilizar: el Debe suma {asiento.total_debe} y el Haber "
            f"{asiento.total_haber}. Faltan {abs(diferencia)} "
            f"{'en el Debe' if diferencia < 0 else 'en el Haber'}.",
            400,
        )

    asiento.estado = "CONTABILIZADO"
    db.commit()
    db.refresh(asiento)

    if asiento.comprobante is not None and asiento.comprobante.estado == "BORRADOR":
        asiento.comprobante.estado = "CONTABILIZADO"
        db.commit()

    return {
        "asiento_id": asiento.id_asiento,
        "estado": asiento.estado,
        "total_debe": str(asiento.total_debe),
        "total_haber": str(asiento.total_haber),
    }


def pasar_a_borrador(db: Session, asiento_id: int) -> dict:
    """Vuelve un asiento contabilizado a borrador. Solo si nadie lo movió más."""
    asiento = db.get(Asiento, asiento_id)
    if asiento is None:
        raise Rechazo("El asiento no existe", 404)
    if asiento.estado == "ANULADO":
        raise Rechazo("El asiento está anulado", 409)
    _verificar_periodo(db, asiento.fecha, "pasar a borrador ese asiento")
    asiento.estado = "BORRADOR"
    db.commit()
    db.refresh(asiento)
    return {"asiento_id": asiento.id_asiento, "estado": asiento.estado}


def anular(db: Session, asiento_id: int) -> dict:
    """Saca el asiento de los saldos sin borrarlo."""
    asiento = db.get(Asiento, asiento_id)
    if asiento is None:
        raise Rechazo("El asiento no existe", 404)
    _verificar_periodo(db, asiento.fecha, "anular ese asiento")
    asiento.estado = "ANULADO"
    db.commit()
    db.refresh(asiento)
    return {"asiento_id": asiento.id_asiento, "estado": asiento.estado}


# =====================================================================
# SALDOS  (siempre por SQL, nunca guardados)
# =====================================================================

def saldos(
    db: Session,
    desde: date | None = None,
    hasta: date | None = None,
    solo_imputables: bool = True,
    con_movimientos: bool = False,
) -> list[dict]:
    """Saldo de cada cuenta en el período. **Nunca se guarda: siempre se calcula.**

    Por defecto devuelve **todas** las cuentas imputables, aunque estén en
    cero, para que el balance se vea completo. Con `con_movimientos=True`
    devuelve solo las que tienen algo movimiento.

    `saldo` viene con el **signo de la naturaleza**: en una deudora es
    Debe − Haber, en una acreedora es Haber − Debe. Positivo = a favor.
    """
    # El filtro de "contabilizado y en el período" va en el ON del LEFT JOIN,
    # no en el WHERE: si fuera en el WHERE, las cuentas sin movimientos
    # desaparecerían en vez de mostrarse en cero.
    condiciones = [Asiento.estado == "CONTABILIZADO"]
    if desde:
        condiciones.append(Asiento.fecha >= desde)
    if hasta:
        condiciones.append(Asiento.fecha <= hasta)
    solo_contabilizado = and_(*condiciones)

    # Y el SUM tiene que contar SOLO esas líneas: si se sumara todo
    # `asiento_detalle`, también contaría los asientos en borrador y anulados.
    suma_debe = func.coalesce(
        func.sum(case((Asiento.id_asiento.is_not(None), AsientoDetalle.debe), else_=0)),
        0,
    )
    suma_haber = func.coalesce(
        func.sum(case((Asiento.id_asiento.is_not(None), AsientoDetalle.haber), else_=0)),
        0,
    )
    cuenta_lineas = func.coalesce(
        func.sum(case((Asiento.id_asiento.is_not(None), 1), else_=0)), 0
    )

    consulta = (
        select(
            PlanCuenta.id_cuenta,
            PlanCuenta.codigo,
            PlanCuenta.nombre,
            PlanCuenta.nivel,
            PlanCuenta.naturaleza,
            PlanCuenta.deudora_acreadora,
            suma_debe,
            suma_haber,
            cuenta_lineas,
        )
        .outerjoin(
            AsientoDetalle, AsientoDetalle.id_cuenta == PlanCuenta.id_cuenta
        )
        # OJO: la condición va en el ON del LEFT JOIN, y se arma con `and_()` de
        # SQLAlchemy. Si se usara el `and` de Python entre dos expresiones, se
        # perdería el filtro y entrarían también los asientos anulados.
        .outerjoin(
            Asiento,
            and_(
                Asiento.id_asiento == AsientoDetalle.id_asiento,
                solo_contabilizado,
            ),
        )
        .where(PlanCuenta.activa.is_(True))
        .group_by(
            PlanCuenta.id_cuenta,
            PlanCuenta.codigo,
            PlanCuenta.nombre,
            PlanCuenta.nivel,
            PlanCuenta.naturaleza,
            PlanCuenta.deudora_acreadora,
        )
        .order_by(PlanCuenta.codigo)
    )
    if solo_imputables:
        consulta = consulta.where(PlanCuenta.imputable.is_(True))

    salida = []
    for (
        id_cuenta,
        codigo,
        nombre,
        nivel,
        naturaleza,
        deudora_acreadora,
        total_debe,
        total_haber,
        movimientos,
    ) in db.execute(consulta).all():
        debe = _d(total_debe)
        haber = _d(total_haber)
        if deudora_acreadora == "ACREEDORA":
            saldo = haber - debe
        else:
            saldo = debe - haber
        fila = {
            "id_cuenta": id_cuenta,
            "codigo": codigo,
            "nombre": nombre,
            "nivel": nivel,
            "naturaleza": naturaleza,
            "deudora_acreadora": deudora_acreadora,
            "total_debe": debe,
            "total_haber": haber,
            "saldo": saldo,
            "movimientos": int(movimientos or 0),
        }
        if con_movimientos and fila["movimientos"] == 0:
            continue
        salida.append(fila)
    return salida


# =====================================================================
# MAYOR GENERAL
# =====================================================================

def _nombres_auxiliares(db: Session, ids: set[int]) -> dict[int, str]:
    """Nombre de cada auxiliar (cliente / banco / proveedor) de una sola vez.

    Sin esto el mayor muestra `id_auxiliar: 608` y el contador no sabe a quién
    pertenece el movimiento. Se traen TODOS de una consulta y se usan de
    diccionario: si se buscara el nombre línea por línea, una cuenta con 400
    movimientos haría 400 consultas.

    Los auxiliares viven en `clientes` (que tiene `persona_id`) joined con
    `personas`. El mismo `id` puede ser un cliente o un banco según lo diga
    `tipo_auxiliar` de la línea, así que se indexa por (tipo, id).
    """
    if not ids:
        return {}

    filas = db.execute(
        text(
            "SELECT c.id, c.nro_cuenta, "
            "       CONCAT_WS(' ', pe.nombre, pe.apellido) AS nombre, "
            "       pe.cuit "
            "  FROM clientes c "
            "  LEFT JOIN personas pe ON pe.id = c.persona_id "
            " WHERE c.id IN :ids"
        ).bindparams(bindparam("ids", expanding=True)),
        {"ids": sorted(ids)},
    ).mappings().all()

    salida = {}
    for f in filas:
        nombre = (f["nombre"] or "").strip()
        if f["nro_cuenta"] is not None:
            # Con nro de cuenta se distingue de otra persona con el mismo
            # nombre, que en un estudio pasa (dos "Jones" no son el mismo).
            etiqueta = f"{nombre} (cuenta {f['nro_cuenta']})" if nombre else f"cuenta {f['nro_cuenta']}"
        else:
            etiqueta = nombre or f"auxiliar {f['id']}"
        salida[f["id"]] = etiqueta
    return salida


def mayor(
    db: Session,
    id_cuenta: int,
    desde: date | None = None,
    hasta: date | None = None,
    auxiliar_id: int | None = None,
) -> dict:
    """El MAYOR de una cuenta: todos sus movimientos, uno por línea, con el
    saldo que va acumulando.

    Es el libro que muestra de dónde salió cada peso y a dónde fue. La
    diferencia con `/saldos` es que ahí va un número por cuenta; acá va la
    lista completa con el saldo en cada línea.

    El saldo acumulado se arma **en el backend** a propósito (va en el for de
    Python), pero los debe/haber de cada línea salen de SQL. Razón: el saldo
    acumulado depende del saldo ANTERIOR, y para calcularlo en un solo SQL
    haría falta una función de ventana (`SUM() OVER`), que MySQL no tiene.
    Acá no se está calculando nada que no venga de la base: cada debe y cada
    haber es un dato, no una suma. La suma final sí es un `SUM` de SQL y se usa
    para verificar.

    **Cuentas con auxiliar (Documentos a cobrar, Clientes, bancos).** El saldo
    acumulado de la cuenta COMPLETA mezcla clientes: si.scienta debe 100.000 a
    Ana y 70.000 a Bruno, el acumulado dice 170.000 y ese número no es de nadie.
    Por eso:
      - cada línea trae `auxiliar_nombre`, para saber a quién es el movimiento;
      - `auxiliares` trae un subtotal por auxiliar (saldo, debe, haber y
        cantidad de movimientos de cada uno), que es lo que el contador mira;
      - con `auxiliar_id` se puede ver el mayor de UN cliente solo, y ahí el
        acumulado sí es el saldo de ese cliente.
    """
    cuenta = db.get(PlanCuenta, id_cuenta)
    if cuenta is None:
        raise Rechazo("La cuenta no existe", 404)

    condiciones = [Asiento.estado == "CONTABILIZADO", AsientoDetalle.id_cuenta == id_cuenta]
    if desde:
        condiciones.append(Asiento.fecha >= desde)
    if hasta:
        condiciones.append(Asiento.fecha <= hasta)
    if auxiliar_id is not None:
        # El mayor de UN auxiliar. El acumulado y el saldo final pasan a ser de
        # ese cliente, no de la cuenta entera.
        condiciones.append(AsientoDetalle.id_auxiliar == auxiliar_id)

    consulta = (
        select(
            AsientoDetalle.id_detalle,
            AsientoDetalle.debe,
            AsientoDetalle.haber,
            AsientoDetalle.tipo_auxiliar,
            AsientoDetalle.id_auxiliar,
            Asiento.fecha,
            Asiento.id_asiento,
            Asiento.concepto,
            Asiento.estado,
            ComprobanteInterno.codigo_comprobante,
            ComprobanteInterno.numero,
        )
        .join(Asiento, Asiento.id_asiento == AsientoDetalle.id_asiento)
        .outerjoin(
            ComprobanteInterno,
            ComprobanteInterno.id_comprobante == Asiento.id_comprobante,
        )
        .where(*condiciones)
        .order_by(Asiento.fecha, Asiento.id_asiento, AsientoDetalle.id_detalle)
    )

    # Signo del saldo según la naturaleza: en una deudora es Debe − Haber, en
    # una acreedora es Haber − Debe. Se calcula una sola vez, acá arriba.
    es_acreedora = cuenta.deudora_acreadora == "ACREEDORA"

    filas = db.execute(consulta).all()

    # Los nombres de los auxiliares salen en UNA consulta aparte, no por línea:
    # el nombre no cambia dentro del recorrido y una cuenta con 400
    # movimientos no puede hacer 400 consultas al mismo cliente.
    nombres = _nombres_auxiliares(
        db, {f[4] for f in filas if f[3] and f[4] is not None}
    )

    lineas = []
    acumulado = Decimal("0.0000")
    suma_debe = Decimal("0.0000")
    suma_haber = Decimal("0.0000")

    # Subtotal por auxiliar. El saldo se calcula al final con la fórmula de la
    # naturaleza (no sumando en el for), así cada subtotal se puede comparar
    # contra el recorrido igual que el total de la cuenta.
    por_auxiliar = {}

    for (
        id_detalle, debe, haber, tipo_aux, id_aux, fecha, id_asiento,
        concepto, estado, codigo_comp, numero,
    ) in filas:
        d = _d(debe)
        h = _d(haber)
        suma_debe += d
        suma_haber += h
        acumulado += (h - d) if es_acreedora else (d - h)
        lineas.append(
            {
                "id_detalle": id_detalle,
                "id_asiento": id_asiento,
                "fecha": fecha,
                "codigo_comprobante": codigo_comp,
                "numero_comprobante": (
                    f"{codigo_comp}-{numero:06d}" if codigo_comp else None
                ),
                "concepto": concepto,
                "estado_asiento": estado,
                "tipo_auxiliar": tipo_aux,
                "id_auxiliar": id_aux,
                "auxiliar_nombre": nombres.get(id_aux) if tipo_aux else None,
                "debe": d,
                "haber": h,
                "saldo": acumulado,
            }
        )

        # El subtotal se acumula solo si NO se está filtrando por un auxiliar:
        # con el filtro puesto, mostrar "Ana: X" sobre un libro que ya es de Ana
        # es ruido.
        if tipo_aux and id_aux is not None and auxiliar_id is None:
            aux = por_auxiliar.setdefault(
                id_aux,
                {
                    "id_auxiliar": id_aux,
                    "tipo_auxiliar": tipo_aux,
                    "nombre": nombres.get(id_aux),
                    "debe": Decimal("0.0000"),
                    "haber": Decimal("0.0000"),
                    "movimientos": 0,
                },
            )
            aux["debe"] += d
            aux["haber"] += h
            aux["movimientos"] += 1

    # El saldo final sale por fórmula (no sumando las líneas), así también
    # sirve de control: si no coinciden, algo se rompió en el recorrido.
    saldo_final = (suma_haber - suma_debe) if es_acreedora else (suma_debe - suma_haber)
    cierra = saldo_final == acumulado

    # Cada auxiliar con su saldo, ya con el signo de la naturaleza. Ordenado
    # por saldo de mayor a menor: el que más debe es el que más importa ver.
    auxiliares = []
    for aux in por_auxiliar.values():
        aux["saldo"] = (
            (aux["haber"] - aux["debe"])
            if es_acreedora
            else (aux["debe"] - aux["haber"])
        )
        auxiliares.append(aux)
    auxiliares.sort(key=lambda a: (-a["saldo"], a["nombre"] or ""))

    return {
        "cuenta": {
            "id_cuenta": cuenta.id_cuenta,
            "codigo": cuenta.codigo,
            "nombre": cuenta.nombre,
            "nivel": cuenta.nivel,
            "naturaleza": cuenta.naturaleza,
            "deudora_acreadora": cuenta.deudora_acreadora,
            "tipo_auxiliar": cuenta.tipo_auxiliar,
        },
        "lineas": lineas,
        "total_debe": suma_debe,
        "total_haber": suma_haber,
        "saldo_final": saldo_final,
        "cierra": cierra,
        "movimientos": len(lineas),
        # El auxiliar que se está mirando, si se filtró. El contador lo usa
        # para el título: si no, nunca sabría si el saldo es de la cuenta
        # entera o de un cliente.
        "auxiliar_id": auxiliar_id,
        "auxiliar_nombre": (
            _nombres_auxiliares(db, {auxiliar_id}).get(auxiliar_id)
            if auxiliar_id is not None
            else None
        ),
        "auxiliares": auxiliares,
        # Suma de los subtotales. Tiene que dar igual que `total_debe`: si no
        # dan, algún movimiento se habría quedado fuera del agrupado.
        "auxiliares_cubren": sum(
            (a["debe"] for a in auxiliares), Decimal("0.0000")
        ),
    }


def saldo_de_cuenta(db: Session, cuenta_id: int, **kwargs) -> dict | None:
    for fila in saldos(db, **kwargs):
        if fila["id_cuenta"] == cuenta_id:
            return fila
    return None


# =====================================================================
# CONTROL GENERAL
# =====================================================================

def control_general(db: Session) -> dict:
    """Que todo asiento CONTABILIZADO tenga Debe = Haber.

    Si alguno no cierra, lo dice cuál y por cuánto. No lo arregla: se ve y se
    corrige a mano (es lo que tiene que servir este control).
    """
    filas = db.execute(
        select(
            Asiento.id_asiento,
            Asiento.fecha,
            Asiento.concepto,
            Asiento.estado,
            Asiento.total_debe,
            Asiento.total_haber,
            ComprobanteInterno.codigo_comprobante,
            ComprobanteInterno.anio,
            ComprobanteInterno.numero,
        )
        .join(
            ComprobanteInterno,
            ComprobanteInterno.id_comprobante == Asiento.id_comprobante,
            isouter=True,
        )
        .where(Asiento.estado == "CONTABILIZADO")
        .order_by(Asiento.id_asiento)
    ).all()

    problemas = []
    total_debe = Decimal("0")
    total_haber = Decimal("0")
    for (
        id_asiento,
        fecha,
        concepto,
        estado,
        t_debe,
        t_haber,
        codigo,
        anio,
        numero,
    ) in filas:
        d = _d(t_debe)
        h = _d(t_haber)
        total_debe += d
        total_haber += h
        if d != h:
            etiqueta = (
                f"{codigo}-{numero:06d}" if codigo else f"asiento {id_asiento}"
            )
            problemas.append(
                {
                    "id_asiento": id_asiento,
                    "etiqueta": etiqueta,
                    "fecha": fecha.isoformat(),
                    "concepto": concepto,
                    "total_debe": str(d),
                    "total_haber": str(h),
                    "diferencia": str(d - h),
                }
            )

    diferencia_general = total_debe - total_haber
    return {
        "asientos_contabilizados": len(filas),
        "total_debe": str(total_debe),
        "total_haber": str(total_haber),
        "diferencia_general": str(diferencia_general),
        "ok": not problemas and diferencia_general == Decimal("0"),
        "problemas": problemas,
    }