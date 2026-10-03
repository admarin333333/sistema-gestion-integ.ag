from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font
from sqlalchemy import bindparam, func, text
from sqlalchemy.orm import Session

from app.config import settings
from app.core.errors import Rechazo
from app.models.alicuota import AlicuotaIva
from app.models.compra import ESTADOS_COMPRA, Compra
from app.models.asiento_origen import AsientoOrigen
from app.models.plan_cuenta import PlanCuenta
from app.models.proveedor import Proveedor
from app.schemas.compra import CompraActualizar, CompraCrear
from app.schemas.factura import ETIQUETAS_TIPO

# La rama de GASTOS del plan. Una cuenta de gasto de compra tiene que estar acá
# adentro, si no el gasto no aparecería en el informe por centro de costos.
CODIGO_RAIZ_GASTOS = "6"


def _condiciones(proveedor_id, desde, hasta) -> list:
    condiciones = []
    if proveedor_id is not None:
        condiciones.append(Compra.proveedor_id == proveedor_id)
    if desde is not None:
        condiciones.append(Compra.fecha >= desde)
    if hasta is not None:
        condiciones.append(Compra.fecha <= hasta)
    return condiciones


def listar(
    db: Session,
    proveedor_id: int | None = None,
    desde=None,
    hasta=None,
    sin_asiento: bool = False,
) -> list[Compra]:
    consulta = (
        db.query(Compra)
        .filter(*_condiciones(proveedor_id, desde, hasta))
        .order_by(Compra.fecha.desc(), Compra.id.desc())
    )
    if sin_asiento:
        # Lo mismo que en los recibos: un NOT EXISTS en SQL, no filtrar en el
        # navegador. Si no, el contador ve 40 filas y el "son 40" de abajo no
        # cuadra con lo que se está mostrando.
        consulta = consulta.filter(
            ~Compra.id.in_(
                db.query(AsientoOrigen.id_compra).filter(
                    AsientoOrigen.origen == "COMPRA",
                    AsientoOrigen.id_compra.isnot(None),
                )
            )
        )
    compras = consulta.all()
    asientos = _asientos_por_compra(db, compras)
    for c in compras:
        a = asientos.get(c.id)
        c.id_asiento = a["id_asiento"] if a else None
        c.estado_asiento = a["estado"] if a else None
        c.numero_comprobante_asiento = a["numero_completo"] if a else None
    return compras


def total(
    db: Session,
    proveedor_id: int | None = None,
    desde=None,
    hasta=None,
) -> float:
    """Suma de totales — se calcula SIEMPRE con SQL, nunca en el navegador."""
    valor = (
        db.query(func.sum(Compra.total))
        .filter(*_condiciones(proveedor_id, desde, hasta))
        .scalar()
    )
    return float(valor or 0)


def obtener(db: Session, compra_id: int) -> Compra:
    compra = db.get(Compra, compra_id)
    if compra is None:
        raise Rechazo("No existe ese comprobante", 404)
    return _con_asiento(db, compra)


def _con_asiento(db: Session, compra: Compra) -> Compra:
    """Le cuelga a la compra su asiento (id, estado, número de comprobante).

    `id_asiento` / `estado_asiento` / `numero_comprobante_asiento` NO son
    columnas: se calculan acá y se agregan al objeto en memoria. Si se
    declararan con `Mapped[...]` en el modelo, SQLAlchemy crearía las columnas
    y la información quedaría duplicada en dos lugares (y desactualizada).

    Una consulta para todas las compras de la lista, no una por fila: el listado
    puede traer 300 compras y con eso serían 300 viajes a la base.
    """
    if compra.id is None:
        return compra
    a = _asiento_de(db, compra.id)
    compra.id_asiento = a["id_asiento"] if a else None
    compra.estado_asiento = a["estado"] if a else None
    compra.numero_comprobante_asiento = a["numero_completo"] if a else None
    return compra


def _asientos_por_compra(db: Session, compras: list[Compra]) -> dict[int, dict]:
    """El asiento de cada compra, en una sola consulta."""
    if not compras:
        return {}
    ids = [c.id for c in compras]
    filas = db.execute(
        text(
            "SELECT o.id_compra, a.id_asiento, a.estado, ci.codigo_comprobante, "
            "       ci.numero "
            "FROM asiento_origen o "
            "JOIN asientos a ON a.id_asiento = o.id_asiento "
            "LEFT JOIN comprobantes_internos ci "
            "       ON ci.id_comprobante = a.id_comprobante "
            "WHERE o.origen = 'COMPRA' AND o.id_compra IN :ids"
        ).bindparams(bindparam("ids", expanding=True)),
        {"ids": ids},
    ).all()
    return {
        f[0]: {
            "id_asiento": f[1],
            "estado": f[2],
            "numero_completo": (
                f"{f[3]}-{int(f[4]):06d}" if f[3] and f[4] is not None else None
            ),
        }
        for f in filas
    }


def _asiento_de(db: Session, compra_id: int) -> dict | None:
    """El asiento de UNA compra (o None si todavía no está asentada)."""
    return _asientos_por_compra(db, [db.get(Compra, compra_id)]).get(compra_id)


def _verificar_unico(db: Session, datos, excluye: int | None = None) -> None:
    consulta = db.query(Compra).filter(
        Compra.proveedor_id == datos.proveedor_id,
        Compra.tipo_comprobante == datos.tipo_comprobante,
        Compra.punto_venta == datos.punto_venta,
        Compra.numero == datos.numero,
    )
    if excluye:
        consulta = consulta.filter(Compra.id != excluye)
    if consulta.first():
        raise Rechazo(
            f"Ya existe {ETIQUETAS_TIPO[datos.tipo_comprobante]} "
            f"{datos.punto_venta}-{datos.numero} de ese proveedor",
            409,
        )


def _verificar_referencias(db: Session, datos) -> AlicuotaIva:
    # El proveedor sale de `proveedores`, no de `clientes`: son tablas distintas
    # (los datos de la persona viven en `personas`). Antes se buscaba en
    # `clientes` y se chequeaba un `.tipo` que esa tabla no tiene, así que
    # cargar una compra reventaba siempre con un error 500.
    proveedor = db.get(Proveedor, datos.proveedor_id)
    if proveedor is None:
        raise Rechazo("No existe ese proveedor", 404)

    alicuota = db.get(AlicuotaIva, datos.alicuota_iva_id)
    if alicuota is None or not alicuota.activo:
        raise Rechazo("Elegí una alícuota de IVA válida", 409)

    _verificar_cuenta_gasto(db, datos.cuenta_gasto_id)
    return alicuota


def _verificar_cuenta_gasto(db: Session, cuenta_gasto_id: int) -> PlanCuenta:
    """La cuenta de gasto tiene que ser una imputable de la rama 6 (GASTOS).

    Se valida acá y no solo al generar el asiento, para que una compra no pueda
    quedar guardada con una cuenta que después no sirve para asentar. Además el
    mensaje es el que ve el contador al cargar, no un error técnico al apretar
    "Asentar" tres pantallas más adelante.
    """
    cuenta = db.get(PlanCuenta, cuenta_gasto_id)
    if cuenta is None or not cuenta.activa:
        raise Rechazo("Elegí una cuenta de gasto válida", 409)
    if not cuenta.imputable:
        raise Rechazo(
            f"{cuenta.codigo} {cuenta.nombre} es un agrupador: no recibe "
            "movimientos. Elegí una cuenta concreta.",
            409,
        )
    if not cuenta.codigo.startswith(CODIGO_RAIZ_GASTOS + "."):
        raise Rechazo(
            f"{cuenta.codigo} {cuenta.nombre} no es una cuenta de gasto "
            f"(tiene que estar bajo {CODIGO_RAIZ_GASTOS} GASTOS). Si no, el "
            "gasto no aparecería en el informe por centro de costos.",
            409,
        )
    return cuenta


def _calcular(neto: float, porcentaje: float, percepcion: float) -> tuple[float, float]:
    """IVA = neto × alícuota · Total = neto + IVA + percepción (todo acá)."""
    iva = (
        Decimal(str(neto)) * Decimal(str(porcentaje)) / 100
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    total = (
        Decimal(str(neto)) + iva + Decimal(str(percepcion))
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return float(iva), float(total)


def _verificar_periodo(db: Session, fecha, que: str) -> None:
    """Frena si la fecha cae en un período contable cerrado.

    Va en un `_` para que quede claro que es una guarda, no una función de
    negocio: en facturas, recibos y compras se llama en el MISMO lugar (primera
    línea de cada escritura) y tiene que decir lo mismo siempre.
    """
    from app.services import periodo_service

    periodo_service.verificar_abierto(db, fecha, que)


def crear(db: Session, datos: CompraCrear) -> Compra:
    _verificar_periodo(db, datos.fecha, "cargar una compra con esa fecha")
    alicuota = _verificar_referencias(db, datos)
    _verificar_unico(db, datos)
    iva, total = _calcular(datos.neto, float(alicuota.porcentaje), datos.percepcion_iva)
    compra = Compra(**datos.model_dump(), iva=iva, total=total)
    db.add(compra)
    db.commit()
    db.refresh(compra)
    return compra


def actualizar(db: Session, compra_id: int, datos: CompraActualizar) -> Compra:
    compra = obtener(db, compra_id)
    _verificar_periodo(db, compra.fecha, "modificar esa compra")
    if compra.estado == "anulada":
        raise Rechazo("No se puede modificar un comprobante anulado", 409)
    alicuota = _verificar_referencias(db, datos)
    _verificar_unico(db, datos, excluye=compra_id)
    iva, total = _calcular(datos.neto, float(alicuota.porcentaje), datos.percepcion_iva)
    for campo, valor in datos.model_dump().items():
        setattr(compra, campo, valor)
    compra.iva = iva
    compra.total = total
    compra.actualizado = datetime.utcnow()
    db.commit()
    db.refresh(compra)
    return compra


def anular(db: Session, compra_id: int) -> Compra:
    """Anula la compra. Solo admin (el rol se controla en el router).

    Anular la compra NO anula el asiento: son dos cosas distintas, igual que con
    las facturas. Si el asiento sigue contabilizado, el gasto sigue en el
    informe por centro de costos y el contador tiene que anular el asiento desde
    la pantalla del asiento. Por eso el mensaje dice las dos cosas.
    """
    compra = obtener(db, compra_id)
    _verificar_periodo(db, compra.fecha, "anular esa compra")
    compra.estado = "anulada"
    compra.actualizado = datetime.utcnow()
    db.commit()
    db.refresh(compra)
    return _con_asiento(db, compra)


def reabrir(db: Session, compra_id: int) -> Compra:
    compra = obtener(db, compra_id)
    _verificar_periodo(db, compra.fecha, "reabrir esa compra")
    compra.estado = "pendiente"
    compra.actualizado = datetime.utcnow()
    db.commit()
    db.refresh(compra)
    return _con_asiento(db, compra)


def eliminar(db: Session, compra_id: int) -> None:
    """Una compra con asiento NO se borra.

    Es la misma regla que las facturas: el asiento es un documento contable. Si
    estuviera contabilizado, borrarla dejaría el movimiento en los libros sin
    respaldo. El que se puede es anular.
    """
    compra = obtener(db, compra_id)
    _verificar_periodo(db, compra.fecha, "eliminar esa compra")
    if getattr(compra, "id_asiento", None):
        raise Rechazo(
            "La compra tiene asiento y no se puede borrar: el asiento es un "
            "documento contable. Anulá la compra y anulá el asiento.",
            409,
        )
    db.delete(compra)
    db.commit()


# --------------------------------------------------------------------- Excel

def _cuenta_texto(c: Compra) -> str:
    """La cuenta de gasto como se muestra: "6.1.03 luz-agua"."""
    return (
        f"{c.cuenta_gasto.codigo} {c.cuenta_gasto.nombre}" if c.cuenta_gasto else ""
    )


def _asiento_texto(c: Compra) -> str:
    """El número de comprobante del asiento, si la compra ya está asentada."""
    return getattr(c, "numero_comprobante_asiento", None) or "sin asentar"


def informe_excel(compras: list[Compra], total_general: float) -> bytes:
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Compras"
    columnas = [
        ("Fecha", 12),
        ("Tipo", 20),
        ("Punto de venta", 15),
        ("Número", 12),
        ("Proveedor", 30),
        ("Concepto", 40),
        ("Neto", 14),
        ("IVA", 14),
        ("Percepción", 14),
        ("Total", 14),
        ("Cuenta de gasto", 30),
        ("Centro", 26),
        ("Asiento", 14),
        ("Estado", 14),
    ]
    hoja.append([settings.nombre_estudio])
    hoja.cell(row=1, column=1).font = Font(bold=True, size=13)
    hoja.append([])

    hoja.append([nombre for nombre, _ in columnas])
    for celda in hoja[3]:
        celda.font = Font(bold=True)

    for c in compras:
        hoja.append(
            [
                c.fecha.isoformat(),
                ETIQUETAS_TIPO.get(c.tipo_comprobante, c.tipo_comprobante),
                c.punto_venta,
                c.numero,
                c.proveedor_nombre,
                c.concepto or "",
                float(c.neto),
                float(c.iva),
                float(c.percepcion_iva),
                float(c.total),
                _cuenta_texto(c),
                c.centro_nombre,
                _asiento_texto(c),
                c.estado,
            ]
        )

    hoja.append([""] * len(columnas))
    hoja.append(["", "", "", "", "", "", "", "", "", total_general])
    ultima = hoja.max_row
    hoja.cell(row=ultima, column=10).font = Font(bold=True)
    celda_total = hoja.cell(row=ultima, column=10)
    celda_total.font = Font(bold=True)
    celda_total.number_format = "#,##0.00"

    for (nombre, ancho), letra in zip(columnas, "ABCDEFGHIJKLMN"):
        hoja.column_dimensions[letra].width = ancho

    salida = BytesIO()
    libro.save(salida)
    return salida.getvalue()
