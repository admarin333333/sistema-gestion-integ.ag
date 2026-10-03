from datetime import date, datetime, timedelta
from decimal import Decimal

# Los DÍAS DE PLAZO: una factura vence esta cantidad de días después de su
# fecha. Es el plazo que maneja el contador (lo pidió el 02/10/2026).
#
# Vive acá y no en el router porque lo usa el cálculo del informe. La pantalla
# lo recibe en la respuesta (`dias_plazo`) en vez de tener su propia copia: si
# el número estuviera en los dos lados y uno cambiara, el contador vería una
# factura vencida con un plazo que no coincide con el del formulario.
DIAS_PLAZO = 7
from sqlalchemy import func, or_, and_, case, text
from sqlalchemy.orm import Session

from app.models.factura import Factura, ESTADOS as FACTURA_ESTADOS, TIPOS_COMPROBANTE
from app.models.anticipo import Anticipo, ESTADOS_ANTICIPO
from app.models.recibo import Recibo
from app.models.cliente import Cliente
from app.models.proveedor import Proveedor
from app.models.persona import Persona
from app.models.compra import Compra
from app.models.centrocosto import CentroCosto
from app.models.plan_cuenta import PlanCuenta
from app.models.asiento import Asiento, AsientoDetalle
from app.schemas.constantes import ETIQUETAS_CONDICION_IVA
from app.config import settings
from app.core.errors import Rechazo


def _dec(valor) -> Decimal:
    """Un NULL de SQL (un SUM sobre cero filas) a Decimal cero.

    Sin esto, una cuenta sin movimientos en el período devuelve None y el
    informe explota al restarlo.
    """
    return Decimal(str(valor or 0))



# Etiquetas para tipos de comprobante
ETIQUETAS_TIPO = {
    "factura_a": "Factura A",
    "factura_b": "Factura B",
    "factura_c": "Factura C",
    "nota_credito_a": "Nota de Crédito A",
    "nota_credito_b": "Nota de Crédito B",
    "nota_credito_c": "Nota de Crédito C",
    "nota_debito_a": "Nota de Débito A",
    "nota_debito_b": "Nota de Débito B",
    "nota_debito_c": "Nota de Débito C",
}

ETIQUETAS_ESTADO_FACTURA = {
    "pendiente": "Pendiente",
    "parcial": "Parcialmente pagada",
    "pagada": "Pagada",
    "anulada": "Anulada",
}

ETIQUETAS_ESTADO_ANTICIPO = {
    "disponible": "Disponible",
    "parcial": "Parcial",
    "aplicado": "Aplicado",
    "eliminado": "Eliminado",
}


def _condiciones_fecha(desde, hasta):
    """Condiciones de fecha reutilizables."""
    condiciones = []
    if desde:
        condiciones.append({"desde": desde})
    if hasta:
        condiciones.append({"hasta": hasta})
    return condiciones


def _filtrar_fecha(query, campo_fecha, desde, hasta):
    """Aplica filtros de fecha a una query."""
    if desde:
        query = query.filter(campo_fecha >= desde)
    if hasta:
        query = query.filter(campo_fecha <= hasta)
    return query


def informe_estado_deuda(
    db: Session,
    desde: date = None,
    hasta: date = None,
    cliente_id: int = None,
) -> dict:
    """
    Informe de Estado de Deuda Total.
    Incluye: Facturas, Notas de Crédito, Notas de Débito pendientes de pago.
    Filtros: desde, hasta, cliente_id.
    """
    # Estados que se consideran "pendientes de pago"
    estados_pendientes = ["pendiente", "parcial"]
    
    # Base query para facturas pendientes
    query = db.query(Factura).join(Cliente).filter(
        Factura.estado.in_(estados_pendientes)
    )
    
    if desde:
        query = query.filter(Factura.fecha >= desde)
    if hasta:
        query = query.filter(Factura.fecha <= hasta)
    if cliente_id:
        query = query.filter(Factura.cliente_id == cliente_id)
    
    facturas = query.order_by(Factura.fecha.asc(), Factura.id.asc()).all()
    
    # Calcular totales por tipo de comprobante
    totales = {}
    for f in facturas:
        tipo_label = ETIQUETAS_TIPO.get(f.tipo_comprobante, f.tipo_comprobante)
        if tipo_label not in totales:
            totales[tipo_label] = {"cantidad": 0, "importe": 0.0, "pendiente": 0.0}
        totales[tipo_label]["cantidad"] += 1
        totales[tipo_label]["importe"] += float(f.importe)
        # Calcular pendiente (importe - lo pagado)
        pagado = float(f.importe) - float(f.importe) * (0 if f.estado == "pendiente" else 0.5 if f.estado == "parcial" else 1)
        # Mejor calcular desde aplicaciones
        pendiente = float(f.importe) - pagado
        totales[tipo_label]["pendiente"] += pendiente
    
    # Calcular pendiente real desde aplicaciones de recibo y anticipo
    from app.models.recibo import Aplicacion
    from app.models.anticipo import AplicacionAnticipo
    from sqlalchemy import func
    
    facturas_dict = {f.id: f for f in facturas}
    if facturas_dict:
        # Recibos aplicados
        recibos_aplicados = dict(
            db.query(Aplicacion.factura_id, func.coalesce(func.sum(Aplicacion.importe), 0))
            .filter(Aplicacion.factura_id.in_(facturas_dict.keys()))
            .group_by(Aplicacion.factura_id)
            .all()
        )
        # Anticipos aplicados
        anticipos_aplicados = dict(
            db.query(AplicacionAnticipo.factura_id, func.coalesce(func.sum(AplicacionAnticipo.importe), 0))
            .filter(AplicacionAnticipo.factura_id.in_(facturas_dict.keys()))
            .group_by(AplicacionAnticipo.factura_id)
            .all()
        )
        
        for f in facturas:
            pagado = float(recibos_aplicados.get(f.id, 0)) + float(anticipos_aplicados.get(f.id, 0))
            pendiente = float(f.importe) - pagado
            if pendiente < 0.005:
                pendiente = 0
            f.pendiente_calculado = pendiente
    
    # Agrupar por tipo para totales
    resumen = {}
    for f in facturas:
        tipo = ETIQUETAS_TIPO.get(f.tipo_comprobante, f.tipo_comprobante)
        if tipo not in resumen:
            resumen[tipo] = {"cantidad": 0, "total": 0.0, "pendiente": 0.0}
        resumen[tipo]["cantidad"] += 1
        resumen[tipo]["total"] += float(f.importe)
        resumen[tipo]["pendiente"] += getattr(f, "pendiente_calculado", 0)
    
    # Totales generales
    total_general = sum(r["total"] for r in resumen.values())
    pendiente_general = sum(r["pendiente"] for r in resumen.values())
    
    # Preparar items para la tabla
    #
    # ACÁ ESTÁ LO QUE FALTABA: `dias_vencida`. El informe decía qué facturas
    # estaban pendientes de pago, pero no cuáles ya vencieron. Para el contador
    # son dos cosas distintas: "me deben esto todavía" y "me deben esto desde
    # marzo, hay que ir a cobrarlo".
    #
    # El vencimiento sale de `factura.fecha_vencimiento`, que ahora la pantalla
    # calcula sola a los 7 días. Si una factura vieja no lo tiene, se usa
    # `fecha + DIAS_PLAZO`: es lo mismo que habría dado el cálculo, y evita que
    # las facturas cargadas antes de este cambio salgan todas como "no
    # vencidas" (que es lo que pasaba).
    items = []
    hoy = date.today()
    for f in facturas:
        pendiente = getattr(f, "pendiente_calculado", 0)

        vence = f.fecha_vencimiento or (f.fecha + timedelta(days=DIAS_PLAZO))
        dias = (hoy - vence).days
        # Sin deuda no hay atraso: una factura pagada no "venció".
        vencido = bool(dias > 0 and pendiente > 0.005)

        items.append({
            "fecha": f.fecha.isoformat(),
            # El `cliente_id` no se mostraba en la pantalla, pero sin él el
            # informe de cuenta corriente no puede AGRUPAR por cliente: dos
            # clientes distintos pueden llamarse igual y hay que saber cuál es.
            "cliente_id": f.cliente_id,
            "tipo": ETIQUETAS_TIPO.get(f.tipo_comprobante, f.tipo_comprobante),
            "punto_venta": f.punto_venta,
            "numero": f.numero,
            "cliente": f.cliente.nombre_completo if f.cliente else "",
            "concepto": f.concepto or "",
            "importe": float(f.importe),
            "pendiente": pendiente,
            "estado": ETIQUETAS_ESTADO_FACTURA.get(f.estado, f.estado),
            "fecha_vencimiento": vence.isoformat(),
            "dias_vencida": dias if vencido else 0,
            "vencido": vencido,
        })

    # Los mismos totales, pero solo de lo vencido. Van aparte porque el contador
    # los necesita juntos: "cuánto me deben en total" y "cuánto de eso está
    # vencido" son las dos preguntas del día.
    vencidas = [i for i in items if i["vencido"]]

    return {
        "desde": desde.isoformat() if desde else None,
        "hasta": hasta.isoformat() if hasta else None,
        "cliente_id": cliente_id,
        "items": items,
        "resumen": resumen,
        "total_general": total_general,
        "pendiente_general": pendiente_general,
        "cantidad_total": len(items),
        "cantidad_vencida": len(vencidas),
        "total_vencido": sum(i["pendiente"] for i in vencidas),
        "dias_plazo": DIAS_PLAZO,
        "hoy": hoy.isoformat(),
    }


def informe_cuenta_corriente(
    db: Session,
    desde: date = None,
    hasta: date = None,
    solo_vencidos: bool = False,
) -> dict:
    """
    LA CUENTA CORRIENTE DE TODOS LOS CLIENTES: cuánto debe cada uno, separado en
    vencido y no vencido, con el teléfono para llamar.

    Es el informe del día a día del contador: no el detalle de una factura (eso
    es el estado de deuda, cliente por cliente) sino **la lista de a quién
    llamar**. Por eso van juntos el importe, los días de atraso y el teléfono: con
    los tres a la vista la decisión es tomar el teléfono sin abrir otro lugar.

    Por qué "vencido" y "no vencido" y no solo el total: son dos cobranças
    distintas. Lo vencido hay que ir a buscarlo hoy; lo que todavía tiene plazo se
    cobra solo en su momento. Un total único esconde las dos.

    El teléfono se trae del contacto del cliente. Se arma el número con el código
    de área porque el teléfono solo, sin el 0, no sirve para llamar.

    **El orden es por importe vencido de mayor a menor**, no por apellido. A
    quien va a primarily llamar le interesa el que más debe y más días tiene, no
    el orden alfabético: el orden alfabético pone al final al peor deudor, que es
    justo el que hay que ver primero.
    """
    datos = informe_estado_deuda(db, desde=desde, hasta=hasta, cliente_id=None)

    # Los teléfonos, en una sola consulta: si se pidiera cliente por cliente
    # serían N consultas para armar una tabla.
    ids_clientes = {i["cliente_id"] for i in datos["items"] if i.get("cliente_id")}
    contactos: dict[int, dict] = {}
    if ids_clientes:
        marcas = ",".join(str(i) for i in ids_clientes)
        for c in db.execute(
            text(
                f"SELECT c.id, p.cod_area, p.telefono, p.email "
                f"FROM clientes c JOIN personas p ON p.id = c.persona_id "
                f"WHERE c.id IN ({marcas})"
            )
        ).all():
            cid, area, tel, mail = c
            numero = ""
            if tel:
                # Sin código de área no se puede llamar: se deja el número tal
                # cual y el que lo lea ve que falta el prefijo.
                numero = f"({area}) {tel}" if area else tel
            contactos[cid] = {"telefono": numero, "email": mail or ""}

    por_cliente: dict[int, dict] = {}
    for i in datos["items"]:
        cid = i.get("cliente_id")
        if cid is None:
            # Sin `cliente_id` en el item no se puede agrupar: se agrupa por
            # nombre para no perder la fila.
            cid = f"nombre:{i['cliente']}"
        fila = por_cliente.setdefault(
            cid,
            {
                "cliente_id": i.get("cliente_id"),
                "cliente": i["cliente"],
                "telefono": contactos.get(i.get("cliente_id"), {}).get("telefono", ""),
                "email": contactos.get(i.get("cliente_id"), {}).get("email", ""),
                "pendiente": 0.0,
                "vencido": 0.0,
                "no_vencido": 0.0,
                "comprobantes": 0,
                "vencidos": 0,
                "dias_max": 0,
            },
        )
        fila["comprobantes"] += 1
        fila["pendiente"] += i["pendiente"]
        if i["vencido"]:
            fila["vencido"] += i["pendiente"]
            fila["vencidos"] += 1
            if i["dias_vencida"] > fila["dias_max"]:
                fila["dias_max"] = i["dias_vencida"]
        else:
            fila["no_vencido"] += i["pendiente"]

    items = [f for f in por_cliente.values() if f["pendiente"] > 0.005]

    if solo_vencidos:
        items = [f for f in items if f["vencido"] > 0.005]

    # Primero el que más debe vencido, y a igual monto el que más días tiene.
    items.sort(key=lambda f: (-f["vencido"], -f["dias_max"], f["cliente"].lower()))

    return {
        "desde": desde.isoformat() if desde else None,
        "hasta": hasta.isoformat() if hasta else None,
        "items": items,
        "total_pendiente": sum(f["pendiente"] for f in items),
        "total_vencido": sum(f["vencido"] for f in items),
        "total_no_vencido": sum(f["no_vencido"] for f in items),
        "cantidad_clientes": len(items),
        "cantidad_vencidos": sum(1 for f in items if f["vencido"] > 0.005),
        "sin_telefono": sum(1 for f in items if not f["telefono"]),
        "dias_plazo": DIAS_PLAZO,
        "hoy": date.today().isoformat(),
        "solo_vencidos": solo_vencidos,
    }


def informe_anticipos_pendientes(
    db: Session,
    desde: date = None,
    hasta: date = None,
    cliente_id: int = None,
) -> dict:
    """
    Listado de Anticipos Pendientes de Imputación.
    Estados: disponible, parcial (tienen saldo disponible).
    Filtros: desde, hasta, cliente_id.
    """
    estados_con_saldo = ["disponible", "parcial"]
    
    query = db.query(Anticipo).join(Cliente).filter(
        Anticipo.estado.in_(estados_con_saldo)
    )
    
    if desde:
        query = query.filter(Anticipo.fecha >= desde)
    if hasta:
        query = query.filter(Anticipo.fecha <= hasta)
    if cliente_id:
        query = query.filter(Anticipo.cliente_id == cliente_id)
    
    anticipos = query.order_by(Anticipo.fecha.asc(), Anticipo.id.asc()).all()
    
    from app.models.anticipo import AplicacionAnticipo
    from sqlalchemy import func
    
    # Calcular imputado y disponible para cada anticipo
    if anticipos:
        ids = [a.id for a in anticipos]
        imputados = dict(
            db.query(AplicacionAnticipo.anticipo_id, func.coalesce(func.sum(AplicacionAnticipo.importe), 0))
            .filter(AplicacionAnticipo.anticipo_id.in_(ids))
            .group_by(AplicacionAnticipo.anticipo_id)
            .all()
        )
    
    items = []
    total_importe = 0.0
    total_disponible = 0.0
    total_imputado = 0.0
    
    for a in anticipos:
        imputado = float(imputados.get(a.id, 0))
        disponible = float(a.importe) - imputado
        if disponible < 0.005:
            disponible = 0
        
        total_importe += float(a.importe)
        total_imputado += imputado
        total_disponible += disponible
        
        items.append({
            "fecha": a.fecha.isoformat(),
            "numero": a.numero,
            "cliente": a.cliente.nombre_completo if a.cliente else "",
            "importe": float(a.importe),
            "imputado": imputado,
            "disponible": disponible,
            "estado": ETIQUETAS_ESTADO_ANTICIPO.get(a.estado, a.estado),
        })
    
    resumen = {
        "total_importe": total_importe,
        "total_imputado": total_imputado,
        "total_disponible": total_disponible,
        "cantidad": len(items),
    }
    
    return {
        "desde": desde.isoformat() if desde else None,
        "hasta": hasta.isoformat() if hasta else None,
        "cliente_id": cliente_id,
        "items": items,
        "resumen": resumen,
    }


# --- Listado de proveedores (alta por fecha) ---

def informe_proveedores(
    db: Session,
    desde: date = None,
    hasta: date = None,
) -> dict:
    """Listado de proveedores con alta en el período, ordenado por cuenta."""
    # Desde la separación de módulos (MEMORIA §4.27) los proveedores viven en
    # su propia tabla, no en `clientes`.
    query = db.query(Proveedor).join(Persona, Persona.id == Proveedor.persona_id)
    query = _filtrar_fecha(query, Persona.fecha_alta, desde, hasta)
    proveedores = query.order_by(Proveedor.nro_cuenta.asc()).all()

    items = [
        {
            "nro_cuenta": p.nro_cuenta,
            "nombre": p.nombre_completo,
            "tipo_persona": (
                "Persona jurídica" if p.tipo_persona == "juridica" else "Persona física"
            ),
            "cuit": p.cuit or "",
            "dni": p.dni or "",
            "condicion_iva": ETIQUETAS_CONDICION_IVA.get(
                p.condicion_iva, p.condicion_iva
            ),
            "localidad": p.localidad or "",
            "fecha_alta": p.fecha_alta.isoformat(),
        }
        for p in proveedores
    ]

    return {
        "desde": desde.isoformat() if desde else None,
        "hasta": hasta.isoformat() if hasta else None,
        "items": items,
        "cantidad": len(items),
    }


# --- Ramas del resultado, leídas del plan de cuentas ---

# Las tres ramas del estado de resultado del plan. Los informes no usan las
# tablas de documentos para el resultado: usan ESTAS ramas, leídas de los
# asientos contabilizados. Así el informe de resultados y el de centros de costos
# no pueden decir cosas distintas — es la misma función en los dos.
RAIZ_INGRESOS = "4"
RAIZ_COSTOS = "5"
RAIZ_GASTOS = "6"


def _descendientes(db: Session, id_padre: int) -> list[PlanCuenta]:
    """Todas las cuentas que cuelgan de `id_padre`, a cualquier profundidad.

    Se arma con una consulta por nivel y no con la relación `hijas` para no
    disparar una consulta por cuenta: el plan tiene ~600 cuentas y el informe se
    abre cada vez que el contador mira los números del mes.
    """
    encontradas: list[PlanCuenta] = []
    pendientes = [id_padre]
    vistas: set[int] = set()
    while pendientes:
        actual = pendientes.pop()
        if actual in vistas:
            continue
        vistas.add(actual)
        hijas = (
            db.query(PlanCuenta)
            .filter(PlanCuenta.cuenta_padre_id == actual)
            .order_by(PlanCuenta.codigo)
            .all()
        )
        for h in hijas:
            encontradas.append(h)
            pendientes.append(h.id_cuenta)
    return encontradas


def _arbol_rama(db: Session, codigo_raiz: str, que: str) -> tuple[PlanCuenta, list[dict]]:
    """La rama del plan, como grupos (un nivel abajo de la raíz) con sus cuentas.

    No trae importes: es la estructura. Los grupos son las cuentas que tienen al
    menos una imputable abajo; una agrupadora sin ninguna no es un grupo, es un
    subgroupo más y no se muestra (no tiene nada que mostrar).
    """
    raiz = db.query(PlanCuenta).filter(PlanCuenta.codigo == codigo_raiz).first()
    if raiz is None:
        raise Rechazo(
            f"El plan de cuentas no tiene la cuenta {codigo_raiz} ({que}), de "
            "donde salen los saldos del informe.",
            400,
        )

    grupos = []
    for grupo in _descendientes(db, raiz.id_cuenta):
        cuentas = [c for c in _descendientes(db, grupo.id_cuenta) if c.imputable]
        if not cuentas:
            continue
        grupos.append(
            {
                "id": grupo.id_cuenta,
                "codigo": grupo.codigo,
                "nombre": grupo.nombre,
                "cuentas": cuentas,  # objetos PlanCuenta, no dicts
            }
        )
    return raiz, grupos


def saldos_rama(
    db: Session,
    codigo_raiz: str,
    que: str,
    desde: date = None,
    hasta: date = None,
) -> dict:
    """Saldos de una rama del resultado, **tomados de los libros**.

    Los importes salen de `asiento_detalle` de los asientos **CONTABILIZADOS**:
    una cuenta sin movimientos en el período da 0, esté o no en el plan. Al
    revés de lo que se hacía antes (que sumaba las tablas de facturas y
    compras): un informe tiene que decir lo que está en el libro, no lo que se
    está por cargar.

    **El signo sale de la CUENTA, no de la posición.** Una de ingresos es
    ACREEDORA y su saldo es `haber − debe`; una de gastos o costos es DEUDORA y
    el suyo es `debe − haber`. Por eso el mismo helper sirve para las tres ramas:
    no hay que saber de antemano de qué lado está cada una.

    Los debe/haber de cada cuenta salen de SQL (un `GROUP BY` para toda la
    rama). El total del grupo es la suma de sus cuentas: se arma acá porque el
    plan es un árbol de profundidad variable y un `GROUP BY` por grupo en SQL
    obligaría a duplicar el árbol en un `CASE`. Los importes, todos, vienen de
    la base.
    """
    raiz, grupos = _arbol_rama(db, codigo_raiz, que)

    ids = [c.id_cuenta for g in grupos for c in g["cuentas"]]
    mov: dict[int, tuple[Decimal, Decimal, int]] = {
        i: (Decimal("0"), Decimal("0"), 0) for i in ids
    }

    if ids:
        condiciones = [
            AsientoDetalle.id_cuenta.in_(ids),
            Asiento.estado == "CONTABILIZADO",
        ]
        if desde is not None:
            condiciones.append(Asiento.fecha >= desde)
        if hasta is not None:
            condiciones.append(Asiento.fecha <= hasta)

        filas = (
            db.query(
                AsientoDetalle.id_cuenta,
                func.sum(AsientoDetalle.debe),
                func.sum(AsientoDetalle.haber),
                func.count(AsientoDetalle.id_detalle),
            )
            .join(Asiento, Asiento.id_asiento == AsientoDetalle.id_asiento)
            .filter(*condiciones)
            .group_by(AsientoDetalle.id_cuenta)
            .all()
        )
        for id_cuenta, debe, haber, cantidad in filas:
            mov[id_cuenta] = (_dec(debe), _dec(haber), int(cantidad or 0))

    salida = []
    total_rama = Decimal("0")
    # La raíz (4, 5, 6) es un agrupador y su `deudora_acreadora` es NULL. El
    # signo de la rama se saca de la primera cuenta imputable: dentro de una
    # rama todas las cuentas van del mismo lado (o todas ingresos, o todas
    # gastos), así que una sola alcanza.
    primera = next(
        (c for g in grupos for c in g["cuentas"] if c.deudora_acreadora), None
    )
    rama_deudora = (
        primera.deudora_acreadora != "ACREEDORA" if primera else True
    )

    for g in grupos:
        cuentas = []
        g_debe = g_haber = Decimal("0")
        g_movs = 0
        for c in g["cuentas"]:
            debe, haber, cantidad = mov.get(
                c.id_cuenta, (Decimal("0"), Decimal("0"), 0)
            )
            es_deudora = c.deudora_acreadora != "ACREEDORA"
            total = (debe - haber) if es_deudora else (haber - debe)
            g_debe += debe
            g_haber += haber
            g_movs += cantidad
            cuentas.append(
                {
                    "id": c.id_cuenta,
                    "codigo": c.codigo,
                    "nombre": c.nombre,
                    "total_debe": float(debe),
                    "total_haber": float(haber),
                    "total": float(total),
                    "cantidad_movimientos": cantidad,
                }
            )

        total_g = (g_debe - g_haber) if rama_deudora else (g_haber - g_debe)
        total_rama += total_g
        salida.append(
            {
                "id": g["id"],
                "codigo": g["codigo"],
                "nombre": g["nombre"],
                "total_debe": float(g_debe),
                "total_haber": float(g_haber),
                "total": float(total_g),
                "cantidad_movimientos": g_movs,
                "cuentas": cuentas,
            }
        )

    return {
        "codigo": raiz.codigo,
        "nombre": raiz.nombre,
        "grupos": salida,
        "total": float(total_rama),
    }


def centros_de_costos(db: Session) -> dict:
    """La rama de GASTOS del plan de cuentas, SIN importes.

    La usan las pantallas para mostrar los centros y sus cuentas (para elegir, por
    ejemplo, en qué cuenta se asienta una compra) sin calcular nada.
    """
    raiz, grupos = _arbol_rama(db, RAIZ_GASTOS, "GASTOS")
    return {
        "codigo": raiz.codigo,
        "nombre": raiz.nombre,
        "centros": [
            {
                "id": g["id"],
                "codigo": g["codigo"],
                "nombre": g["nombre"],
                "cuentas": [
                    {
                        "id": c.id_cuenta,
                        "codigo": c.codigo,
                        "nombre": c.nombre,
                    }
                    for c in g["cuentas"]
                ],
            }
            for g in grupos
        ],
    }


def informe_centros(
    db: Session,
    desde: date = None,
    hasta: date = None,
) -> dict:
    """Gastos por centro de costos, tomados de los libros (ver `saldos_rama`)."""
    rama = saldos_rama(db, RAIZ_GASTOS, "GASTOS", desde, hasta)
    return {
        "desde": desde.isoformat() if desde else None,
        "hasta": hasta.isoformat() if hasta else None,
        "raiz": {"codigo": rama["codigo"], "nombre": rama["nombre"]},
        "centros": rama["grupos"],
        "total_general": rama["total"],
    }


# --- Informe de resultados (ingresos - gastos = neto) ---

BIENES_BALANCE = (
    {"n": 1, "nombre": "Mercadería"},
    {"n": 2, "nombre": "Automóvil/Moto"},
)


def informe_resultados(
    db: Session,
    desde: date = None,
    hasta: date = None,
) -> dict:
    """
    Estado de resultado del período, **todo desde los libros**.

        ingresos (rama 4) − costos (rama 5) − gastos (rama 6) = neto

    Los tres lados salen de `saldos_rama`, la misma función que usa el informe
    por centro de costos. Por eso los dos informes **no pueden contradecirse**:
    el gasto que muestra el de resultados es el mismo número que el total de los
    centros.

    Antes el ingreso salía de la tabla de facturas y el gasto de la de compras.
    Eso mezclaba dos fuentes: si una factura estaba cargada pero sin asentar, el
    informe decía "ingreso X" y el libro no tenía nada. Un estado de resultado
    con un lado de los documentos y el otro de los libros no tiene sentido: el
    neto era un número inventado.

    Los BIENES son cuentas de balance (mercadería, útil): NO afectan el neto, y
    por eso van aparte y sin importe.
    """
    ingresos_rama = saldos_rama(db, RAIZ_INGRESOS, "INGRESOS", desde, hasta)
    costos_rama = saldos_rama(db, RAIZ_COSTOS, "COSTOS", desde, hasta)
    gastos_rama = saldos_rama(db, RAIZ_GASTOS, "GASTOS", desde, hasta)

    ingresos = ingresos_rama["total"]
    costos = costos_rama["total"]
    gastos = gastos_rama["total"]

    return {
        "desde": desde.isoformat() if desde else None,
        "hasta": hasta.isoformat() if hasta else None,
        "ingresos": {
            "total": ingresos,
            "cantidad": sum(
                g["cantidad_movimientos"] for g in ingresos_rama["grupos"]
            ),
            "grupos": ingresos_rama["grupos"],
            "nombre_raiz": ingresos_rama["nombre"],
        },
        "costos": {
            "total": costos,
            "cantidad": sum(
                g["cantidad_movimientos"] for g in costos_rama["grupos"]
            ),
            "grupos": costos_rama["grupos"],
            "nombre_raiz": costos_rama["nombre"],
        },
        # Mismos objetos que devuelve `informe_centros`: los gastos de este
        # informe y los del informe por centro son el mismo número.
        "centros": gastos_rama["grupos"],
        "total_gastos": gastos,
        "total_costos": costos,
        "total_egresos": costos + gastos,
        "neto": ingresos - costos - gastos,
        "bienes": [
            {**b, "importe": None, "nota": "Cuenta de balance — no afecta el neto"}
            for b in BIENES_BALANCE
        ],
    }


# --- Excel exports ---

def cuenta_corriente_excel(data: dict) -> bytes:
    """Genera el Excel de la cuenta corriente de todos los clientes.

    El orden de columnas es el del cobro, no el alfabético: primero a quién
    llamar, después cuánto, después si está vencido. Un contador que abre esto
    con intención de llamar no empieza por el apellido.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment
    from io import BytesIO

    wb = Workbook()
    ws = wb.active
    ws.title = "Cuenta corriente"

    ws.append([settings.nombre_estudio])
    ws.cell(row=1, column=1).font = Font(bold=True, size=14)
    ws.append(["CUENTA CORRIENTE — partidas abiertas por cliente"])
    ws.cell(row=2, column=1).font = Font(bold=True, size=12)
    ws.append([
        f"Al {data['hoy']} · plazo {data['dias_plazo']} días"
        + (f" · filtro {data['desde']} a {data['hasta']}" if data.get("desde") else "")
    ])
    ws.append([])

    headers = [
        "Cliente", "Teléfono", "Email", "Comprobantes",
        "Vencido", "No vencido", "Total a cobrar", "Días de atraso",
    ]
    ws.append(headers)
    for cell in ws[ws.max_row]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")

    for f in data["items"]:
        ws.append([
            f["cliente"],
            f["telefono"] or "",
            f["email"] or "",
            f["comprobantes"],
            f["vencido"],
            f["no_vencido"],
            f["pendiente"],
            f["dias_max"],
        ])

    ws.append([])
    ws.append(["TOTALES", "", "", "", data["total_vencido"], data["total_no_vencido"],
               data["total_pendiente"], ""])
    for cell in ws[ws.max_row]:
        cell.font = Font(bold=True)

    # Los importes como número, no como texto: el contador quiere sumar en la
    # planilla y no reescribir las fórmulas.
    for fila in ws.iter_rows(min_row=6, min_col=5, max_col=7):
        for c in fila:
            c.number_format = "#,##0.00"

    bio = BytesIO()
    wb.save(bio)
    return bio.getvalue()


def estado_deuda_excel(data: dict) -> bytes:
    """Genera Excel del informe de estado de deuda."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment
    from io import BytesIO
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Estado de Deuda"
    
    # Encabezado
    ws.append([settings.nombre_estudio])
    ws.cell(row=1, column=1).font = Font(bold=True, size=14)
    ws.append(["ESTADO DE DEUDA TOTAL"])
    ws.cell(row=2, column=1).font = Font(bold=True, size=12)
    
    if data["desde"] or data["hasta"]:
        rango = f"Desde: {data['desde'] or 'inicio'}  Hasta: {data['hasta'] or 'hoy'}"
        ws.append([rango])
    
    ws.append([])
    
    # Items
    # "Días vencida" y "Vencido" van al final: el contador lee primero las fechas
    # y después cuánto atrasado está cada una.
    headers = ["Fecha", "Tipo", "Punto Venta", "Número", "Cliente", "Concepto", "Importe", "Pendiente", "Estado", "Vencimiento", "Días vencida", "Vencido"]
    ws.append(headers)
    for cell in ws[ws.max_row]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")
    
    for item in data["items"]:
        ws.append([
            item["fecha"],
            item["tipo"],
            item["punto_venta"],
            item["numero"],
            item["cliente"],
            item["concepto"],
            item["importe"],
            item["pendiente"],
            item["estado"],
            item["fecha_vencimiento"] or "",
            item.get("dias_vencida", 0),
            "SÍ" if item.get("vencido") else "",
        ])
    
    # Totales
    ws.append([])
    ws.append(["", "", "", "", "TOTALES", "", data["total_general"], data["pendiente_general"], "", ""])
    last_row = ws.max_row
    for col in range(1, len(data["items"][0]) + 1 if data["items"] else 10):
        cell = ws.cell(row=last_row, column=col)
        cell.font = Font(bold=True)
    
    # Ajustar anchos
    for col, width in enumerate([12, 20, 12, 12, 30, 35, 14, 14, 18, 12], 1):
        ws.column_dimensions[chr(64 + col)].width = width
    
    output = BytesIO()
    wb.save(output)
    return output.getvalue()


def anticipos_pendientes_excel(data: dict) -> bytes:
    """Genera Excel del informe de anticipos pendientes."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment
    from io import BytesIO
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Anticipos Pendientes"
    
    ws.append([settings.nombre_estudio])
    ws.cell(row=1, column=1).font = Font(bold=True, size=14)
    ws.append(["ANTICIPOS PENDIENTES DE IMPUTACIÓN"])
    ws.cell(row=2, column=1).font = Font(bold=True, size=12)
    
    if data["desde"] or data["hasta"]:
        ws.append([f"Desde: {data['desde'] or 'inicio'}  Hasta: {data['hasta'] or 'hoy'}"])
    
    ws.append([])
    
    headers = ["Fecha", "Número", "Cliente", "Importe", "Imputado", "Disponible", "Estado"]
    ws.append(headers)
    for cell in ws[ws.max_row]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")
    
    for item in data["items"]:
        ws.append([
            item["fecha"],
            item["numero"],
            item["cliente"],
            item["importe"],
            item["imputado"],
            item["disponible"],
            item["estado"],
        ])
    
    ws.append([])
    ws.append(["", "", "TOTALES", data["resumen"]["total_importe"], data["resumen"]["total_imputado"], data["resumen"]["total_disponible"], ""])
    last_row = ws.max_row
    for col in range(1, 8):
        cell = ws.cell(row=last_row, column=col)
        cell.font = Font(bold=True)
    
    for col, width in enumerate([12, 12, 30, 14, 14, 14, 15], 1):
        ws.column_dimensions[chr(64 + col)].width = width
    
    output = BytesIO()
    wb.save(output)
    return output.getvalue()


def proveedores_excel(data: dict) -> bytes:
    """Excel del listado de proveedores (alta en el período)."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment
    from io import BytesIO

    wb = Workbook()
    ws = wb.active
    ws.title = "Proveedores"

    ws.append([settings.nombre_estudio])
    ws.cell(row=1, column=1).font = Font(bold=True, size=14)
    ws.append(["LISTADO DE PROVEEDORES"])
    ws.cell(row=2, column=1).font = Font(bold=True, size=12)
    if data["desde"] or data["hasta"]:
        ws.append([f"Alta desde: {data['desde'] or 'inicio'}  hasta: {data['hasta'] or 'hoy'}"])
    ws.append([])

    headers = ["Cuenta", "Proveedor", "Tipo", "CUIT", "DNI", "Cond. IVA", "Localidad", "Fecha de alta"]
    ws.append(headers)
    for cell in ws[ws.max_row]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")

    for item in data["items"]:
        ws.append([
            item["nro_cuenta"],
            item["nombre"],
            item["tipo_persona"],
            item["cuit"],
            item["dni"],
            item["condicion_iva"],
            item["localidad"],
            item["fecha_alta"],
        ])

    ws.append([])
    ws.append([f"TOTAL: {data['cantidad']} proveedor(es)"])
    ws.cell(row=ws.max_row, column=1).font = Font(bold=True)

    for col, width in enumerate([9, 34, 16, 15, 12, 20, 20, 14], 1):
        ws.column_dimensions[chr(64 + col)].width = width

    output = BytesIO()
    wb.save(output)
    return output.getvalue()


# --- Informe de CUIT y clave fiscal de ARCA ---

def _ultimo_digito(cuit: str | None) -> str:
    """El último dígito del CUIT: es el que agrupa los vencimientos de ARCA."""
    digitos = "".join(c for c in (cuit or "") if c.isdigit())
    return digitos[-1] if digitos else ""


def informe_claves_fiscales(
    db: Session,
    desde: date = None,
    hasta: date = None,
    terminacion: int | None = None,
) -> dict:
    """Todos los clientes con su CUIT y clave fiscal de ARCA.

    Filtros:
    - `desde` / `hasta`: fecha en que se ** cargó** la clave fiscal.
    - `terminacion`: último dígito del CUIT (0 a 9).

    Viene en dos partes: los que tienen clave fiscal (`items`) y los que no
    (`sin_clave`), para no perder de vista a quién le falta cargarla.
    """
    consulta = db.query(Cliente).join(Persona, Persona.id == Cliente.persona_id)
    consulta = _filtrar_fecha(consulta, Persona.fecha_carga_clave_fiscal, desde, hasta)
    if terminacion is not None:
        # Último dígito del CUIT: se comparan solo los números (el CUIT
        # guardado tiene guiones: "20-26473674-2").
        digitos = func.replace(
            func.replace(func.coalesce(Persona.cuit, ""), "-", ""), ".", ""
        )
        consulta = consulta.filter(func.right(digitos, 1) == str(terminacion))
    filas = consulta.order_by(Cliente.nro_cuenta.asc()).all()

    def _dato(p):
        return {
            "id": p.id,
            "nro_cuenta": p.nro_cuenta,
            "nombre": p.nombre_completo,
            "tipo_persona": (
                "Persona jurídica" if p.tipo_persona == "juridica" else "Persona física"
            ),
            "cuit": p.cuit or "",
            "ultimo_digito": _ultimo_digito(p.cuit),
            "clave_fiscal": p.clave_fiscal or "",
            "fecha_carga_clave_fiscal": (
                p.fecha_carga_clave_fiscal.isoformat()
                if p.fecha_carga_clave_fiscal
                else ""
            ),
            "fecha_modif_clave_fiscal": (
                p.fecha_modif_clave_fiscal.isoformat()
                if p.fecha_modif_clave_fiscal
                else ""
            ),
            "email": p.email or "",
            "localidad": p.localidad or "",
        }

    clientes = list(filas)
    con_clave = [_dato(p) for p in clientes if p.clave_fiscal]
    sin_clave = [_dato(p) for p in clientes if not p.clave_fiscal]

    # Los bloques por terminación, para cargar de a grouped dígitos.
    bloques = []
    for d in range(10):
        del_clave = [i for i in con_clave if i["ultimo_digito"] == str(d)]
        if not del_clave:
            continue
        bloques.append(
            {"ultimo_digito": d, "cantidad": len(del_clave), "items": del_clave}
        )

    return {
        "desde": desde.isoformat() if desde else None,
        "hasta": hasta.isoformat() if hasta else None,
        "terminacion": terminacion,
        "items": con_clave,
        "sin_clave": sin_clave,
        "bloques": bloques,
        "cantidad": len(con_clave),
        "cantidad_sin_clave": len(sin_clave),
    }


def claves_fiscales_excel(data: dict) -> bytes:
    """Excel del informe de CUIT y clave fiscal, agrupado por terminación."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment
    from io import BytesIO

    wb = Workbook()
    ws = wb.active
    ws.title = "Claves fiscales"

    ws.append([settings.nombre_estudio])
    ws.cell(row=1, column=1).font = Font(bold=True, size=14)
    ws.append(["INFORME DE CUIT Y CLAVE FISCAL (ARCA)"])
    ws.cell(row=2, column=1).font = Font(bold=True, size=12)
    filtros = []
    if data["desde"] or data["hasta"]:
        filtros.append(
            f"Clave cargada desde: {data['desde'] or 'inicio'} hasta: {data['hasta'] or 'hoy'}"
        )
    if data["terminacion"] is not None:
        filtros.append(f"CUIT termina en: {data['terminacion']}")
    if filtros:
        ws.append([" · ".join(filtros)])
    ws.append([])

    headers = [
        "Termina en", "Cuenta", "Apellido y nombre / Razón social", "CUIT",
        "Clave fiscal", "Cargada el", "Última modificación", "Email", "Localidad",
    ]

    def _titulo(texto, total):
        ws.append([texto, f"({total})"])
        ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=12)

    def _tabla(items):
        ws.append(headers)
        for cell in ws[ws.max_row]:
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal="center")
        for i in items:
            ws.append([
                i["ultimo_digito"],
                i["nro_cuenta"],
                i["nombre"],
                i["cuit"],
                i["clave_fiscal"],
                i["fecha_carga_clave_fiscal"],
                i["fecha_modif_clave_fiscal"],
                i["email"],
                i["localidad"],
            ])
        ws.append([])

    if data["bloques"]:
        for bloque in data["bloques"]:
            _titulo(f"CUIT termina en {bloque['ultimo_digito']}", bloque["cantidad"])
            _tabla(bloque["items"])
    else:
        _titulo("Con clave fiscal", data["cantidad"])
        _tabla(data["items"])

    if data["sin_clave"]:
        _titulo("SIN CLAVE FISCAL CARGADA", data["cantidad_sin_clave"])
        _tabla(data["sin_clave"])

    ws.append([f"TOTAL con clave fiscal: {data['cantidad']}"])
    ws.cell(row=ws.max_row, column=1).font = Font(bold=True)
    ws.append([f"TOTAL sin clave fiscal: {data['cantidad_sin_clave']}"])
    ws.cell(row=ws.max_row, column=1).font = Font(bold=True)

    for col, width in enumerate([10, 9, 34, 15, 14, 13, 20, 26, 20], 1):
        ws.column_dimensions[chr(64 + col)].width = width

    output = BytesIO()
    wb.save(output)
    return output.getvalue()


def centros_excel(data: dict) -> bytes:
    """Excel del informe por centro de costos, tomado del plan de cuentas.

    Una tabla por centro: sus cuentas de gasto con su importe y el total del
    centro abajo. Es el mismo cuadro que se ve en pantalla.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment
    from openpyxl.utils import get_column_letter
    from io import BytesIO

    wb = Workbook()
    ws = wb.active
    ws.title = "Centros de costos"

    ws.append([settings.nombre_estudio])
    ws.cell(row=1, column=1).font = Font(bold=True, size=14)
    ws.append(["INFORME POR CENTRO DE COSTOS"])
    ws.cell(row=2, column=1).font = Font(bold=True, size=12)
    if data["desde"] or data["hasta"]:
        ws.append(
            [f"Desde: {data['desde'] or 'inicio'}  hasta: {data['hasta'] or 'hoy'}"]
        )
    ws.append(["Importes tomados de los asientos contabilizados."])
    ws.append([])

    headers = ["Código", "Cuenta de gasto", "Movimientos", "Debe", "Haber", "Total"]
    anchos = [12, 40, 13, 16, 16, 16]

    for centro in data["centros"]:
        ws.append([f"{centro['codigo']}  {centro['nombre'].upper()}"])
        fila_centro = ws.max_row
        ws.cell(row=fila_centro, column=1).font = Font(bold=True, size=12)
        ws.cell(row=fila_centro, column=2).font = Font(bold=True, size=12)

        ws.append(headers)
        for cell in ws[ws.max_row]:
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal="center")

        if centro["cantidad_movimientos"] == 0:
            ws.append(["", "Sin movimientos en el período"])
            ws.append([])
            continue

        for c in centro["cuentas"]:
            ws.append([
                c["codigo"], c["nombre"], c["cantidad_movimientos"],
                c["total_debe"], c["total_haber"], c["total"],
            ])

        ws.append([
            "", f"TOTAL {centro['nombre']}", centro["cantidad_movimientos"],
            centro["total_debe"], centro["total_haber"], centro["total"],
        ])
        for col in range(1, 7):
            ws.cell(row=ws.max_row, column=col).font = Font(bold=True)
        ws.append([])

    ws.append(["", "TOTAL GENERAL", "", "", "", data["total_general"]])
    for col in range(1, 7):
        ws.cell(row=ws.max_row, column=col).font = Font(bold=True, size=12)

    for col, width in enumerate(anchos, 1):
        ws.column_dimensions[get_column_letter(col)].width = width

    output = BytesIO()
    wb.save(output)
    return output.getvalue()


def resultados_excel(data: dict) -> bytes:
    """Excel del estado de resultado: ingresos − costos − gastos = neto.

    Es el mismo cuadro que se ve en pantalla, con los importes de los libros.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment
    from openpyxl.utils import get_column_letter
    from io import BytesIO

    wb = Workbook()
    ws = wb.active
    ws.title = "Informe de resultados"

    ws.append([settings.nombre_estudio])
    ws.cell(row=1, column=1).font = Font(bold=True, size=14)
    ws.append(["INFORME DE RESULTADOS"])
    ws.cell(row=2, column=1).font = Font(bold=True, size=12)
    if data["desde"] or data["hasta"]:
        ws.append(
            [f"Desde: {data['desde'] or 'inicio'}  hasta: {data['hasta'] or 'hoy'}"]
        )
    ws.append(["Importes tomados de los asientos contabilizados."])
    ws.append([])

    def bloque(titulo, grupos, total, total_movs):
        """Un bloque del estado: sus grupos con sus cuentas y el total del bloque."""
        ws.append([titulo])
        ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=12)
        ws.append(["Código", "Grupo", "Cuenta", "Movimientos", "Total"])
        for celda in ws[ws.max_row]:
            celda.font = Font(bold=True)
            celda.alignment = Alignment(horizontal="center")
        for g in grupos:
            for k in g["cuentas"]:
                ws.append([k["codigo"], g["nombre"], k["nombre"],
                           k["cantidad_movimientos"], k["total"]])
            ws.append([g["codigo"], f"Total {g['nombre']}", "",
                       g["cantidad_movimientos"], g["total"]])
            for col in range(1, 6):
                ws.cell(row=ws.max_row, column=col).font = Font(bold=True)
        ws.append(["", f"TOTAL {titulo}", "", total_movs, total])
        for col in range(1, 6):
            ws.cell(row=ws.max_row, column=col).font = Font(bold=True, size=12)
        ws.append([])

    bloque(
        "INGRESOS",
        data["ingresos"]["grupos"],
        data["ingresos"]["total"],
        data["ingresos"]["cantidad"],
    )
    bloque(
        "COSTOS",
        data["costos"]["grupos"],
        data["total_costos"],
        data["costos"]["cantidad"],
    )
    bloque("GASTOS", data["centros"], data["total_gastos"],
           sum(c["cantidad_movimientos"] for c in data["centros"]))

    # Neto
    ws.append(["NETO DEL PERÍODO", "", "", "", data["neto"]])
    for col in range(1, 6):
        celda = ws.cell(row=ws.max_row, column=col)
        celda.font = Font(bold=True, size=13)
    ws.append(["", "", "", "", f"{data['ingresos']['total']:,.2f} ingresos "
                  f"− {data['total_costos']:,.2f} costos "
                  f"− {data['total_gastos']:,.2f} gastos"])
    ws.append([])

    # Bienes (cuentas de balance)
    ws.append(["BIENES (cuentas de balance — no afectan el neto)"])
    ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=12)
    ws.append(["N°", "Bien", "Importe", "Observación"])
    for cell in ws[ws.max_row]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")
    for b in data["bienes"]:
        ws.append([
            b["n"], b["nombre"],
            b["importe"] if b["importe"] is not None else "—",
            b["nota"],
        ])

    for col, width in enumerate([14, 34, 34, 14, 18], 1):
        ws.column_dimensions[get_column_letter(col)].width = width

    output = BytesIO()
    wb.save(output)
    return output.getvalue()