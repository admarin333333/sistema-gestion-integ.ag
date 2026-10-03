"""Plan de cuentas: listado, alta, edición y baja.

Reglas que se respetan acá (y que se chequean al cargar el Excel):

1. **El código no se toca.** Es lo que van a referenciar los asientos, así que
   una cuenta se renombra o se apaga, pero su código queda fijo.
2. **Un agrupador no es imputable.** Si la cuenta tiene subcuentas, no puede
   quedar `imputable = TRUE` (si no, el movimiento no tendría dónde imputarse).
   Al revés: si no tiene subcuentas, es una cuenta para asentar.
3. **El `tipo_auxiliar` solo va en las imputables**, y tiene que ser uno de
   CLIENTE / PROVEEDOR / BANCO / NINGUNO.
4. **No se borra una cuenta que tiene subcuentas**: quedaría el árbol colgando.
   Se apaga (`activa = FALSE`), que es distinto de borrar.
"""

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import Rechazo
from app.models.plan_cuenta import PlanCuenta

TIPOS_AUXILIAR = {"CLIENTE", "PROVEEDOR", "BANCO", "NINGUNO"}


def _hijas(db: Session, cuenta_id: int) -> int:
    return (
        db.execute(
            select(func.count(PlanCuenta.id_cuenta)).where(
                PlanCuenta.cuenta_padre_id == cuenta_id
            )
        ).scalar()
        or 0
    )


def _a_json(c: PlanCuenta, tiene_hijas: bool, camino: str) -> dict:
    return {
        "id_cuenta": c.id_cuenta,
        "codigo": c.codigo,
        "nombre": c.nombre,
        "cuenta_padre_id": c.cuenta_padre_id,
        "codigo_padre": None,  # lo completa el listado
        "nivel": c.nivel,
        "naturaleza": c.naturaleza,
        "deudora_acreadora": c.deudora_acreadora,
        "imputable": bool(c.imputable),
        "tipo_auxiliar": c.tipo_auxiliar,
        "activa": bool(c.activa),
        "tiene_hijas": tiene_hijas,
        "camino": camino,
    }


def listar(db: Session, solo_activas: bool = True, buscar: str = "") -> list[dict]:
    """Todas las cuentas, ordenadas por código (que ya viene en orden de árbol).

    `camino` se arma en el servidor: es la línea de texto desde la raíz
    ("1.1 ACTIVO CORRIENTE / 1.1.01 Caja y bancos / Caja"), que es lo que se
    muestra en el buscador para que se entienda dónde está cada cosa.
    """
    consulta = select(PlanCuenta)
    if solo_activas:
        consulta = consulta.where(PlanCuenta.activa.is_(True))
    if buscar:
        texto = f"%{buscar.strip()}%"
        consulta = consulta.where(
            or_(
                PlanCuenta.codigo.like(texto),
                PlanCuenta.nombre.like(texto),
            )
        )
    cuentas = (
        db.execute(consulta.order_by(PlanCuenta.codigo)).scalars().all()
    )

    # Mapa código -> cuenta, para resolver padres y armar el camino.
    todas = {c.codigo: c for c in cuentas}

    # Hijas de cada una (una sola consulta para todas).
    hijos: dict[int, int] = {}
    for padre_id, cantidad in db.execute(
        select(PlanCuenta.cuenta_padre_id, func.count(PlanCuenta.id_cuenta))
        .where(PlanCuenta.cuenta_padre_id.is_not(None))
        .group_by(PlanCuenta.cuenta_padre_id)
    ):
        hijos[padre_id] = cantidad

    def camino_de(c: PlanCuenta) -> str:
        partes = []
        actual: PlanCuenta | None = c
        while actual is not None:
            partes.append(actual.nombre)
            actual = todas.get(actual.codigo.rsplit(".", 1)[0]) if "." in actual.codigo else None
        return " / ".join(reversed(partes))

    salida = []
    for c in cuentas:
        datos = _a_json(c, hijos.get(c.id_cuenta, 0) > 0, camino_de(c))
        if c.cuenta_padre_id:
            padre = db.get(PlanCuenta, c.cuenta_padre_id)
            datos["codigo_padre"] = padre.codigo if padre else None
        salida.append(datos)
    return salida


def buscar_imputables(db: Session, q: str = "", limite: int = 25) -> list[dict]:
    """Cuentas que **reciben movimientos**, para armar las líneas de un asiento.

    Solo `imputable`: una agrupadora ("1.1 ACTIVO CORRIENTE") no se puede
    asentar, así que ofrecerla sería hacer que el contador descubra el error
    recién cuando guarda.

    El filtro busca por código o por nombre. Todas las palabras tienen que
    aparecer (así "caja bancos" no trae 400 cosas).
    """
    consulta = select(PlanCuenta).where(
        PlanCuenta.activa.is_(True), PlanCuenta.imputable.is_(True)
    )
    palabras = [p for p in (q or "").strip().split() if p]
    for palabra in palabras:
        consulta = consulta.where(
            or_(
                PlanCuenta.codigo.like(f"%{palabra}%"),
                PlanCuenta.nombre.like(f"%{palabra}%"),
            )
        )

    cuentas = (
        db.execute(consulta.order_by(PlanCuenta.codigo).limit(limite))
        .scalars()
        .all()
    )
    return [
        {
            "id_cuenta": c.id_cuenta,
            "codigo": c.codigo,
            "nombre": c.nombre,
            "nivel": c.nivel,
            "deudora_acreadora": c.deudora_acreadora,
            "tipo_auxiliar": c.tipo_auxiliar,
        }
        for c in cuentas
    ]


def obtener(db: Session, cuenta_id: int) -> dict:
    c = db.get(PlanCuenta, cuenta_id)
    if c is None:
        raise Rechazo("La cuenta no existe", 404)
    todas = listar(db, solo_activas=False)
    for d in todas:
        if d["id_cuenta"] == cuenta_id:
            return d
    raise Rechazo("La cuenta no existe", 404)   # pragma: no cover


def _chequear_tipo_auxiliar(tipo: str | None, imputable: bool) -> str | None:
    if tipo is None or tipo == "":
        return "NINGUNO" if imputable else None
    if tipo not in TIPOS_AUXILIAR:
        raise Rechazo(
            f"Tipo de auxiliar desconocido: «{tipo}». "
            f"Valores: {', '.join(sorted(TIPOS_AUXILIAR))}.",
            400,
        )
    if not imputable:
        raise Rechazo(
            "El tipo de auxiliar solo se pone en las cuentas imputables", 400
        )
    return tipo


def naturaleza_de(codigo: str) -> str:
    """BALANCE (activo, pasivo, patrimonio neto) o RESULTADO (ingresos, costos...)."""
    return "BALANCE" if codigo.split(".")[0] in ("1", "2", "3") else "RESULTADO"


def deudora_de(codigo: str, nombre: str) -> str:
    """DEUDORA (suma en el Debe) o ACREEDORA (suma en el Haber).

    El grupo 7 (resultados financieros) viene mezclado, así que ahí se decide
    por el nombre: "intereses ganados" y "diferencias positivas" son
    acreedoras; "perdidos" y "negativas" deudoras.
    """
    grupo = codigo.split(".")[0]
    if grupo == "7":
        bajo = (nombre or "").lower()
        if "ganado" in bajo or "positiv" in bajo:
            return "ACREEDORA"
        return "DEUDORA"
    if grupo in ("1", "5", "6"):
        return "DEUDORA"
    return "ACREEDORA"


def crear(
    db: Session, cuenta_padre_id: int, nombre: str, imputable: bool, tipo_auxiliar
) -> dict:
    """Da de alta una cuenta nueva colgando de otra.

    El código se arma solo: el del padre + el siguiente número libre
    (1.1.01.01 Caja -> 1.1.01.02 Fondo fijo -> ...).
    """
    padre = db.get(PlanCuenta, cuenta_padre_id)
    if padre is None:
        raise Rechazo("La cuenta padre no existe", 404)
    if not padre.activa:
        raise Rechazo("No se pueden agregar cuentas a una cuenta apagada", 400)
    if padre.nivel >= 4:
        raise Rechazo(
            "El plan tiene 4 niveles: no se pueden abrir más cuentas abajo de "
            f"{padre.codigo}",
            400,
        )

    nombre = (nombre or "").strip()
    if not nombre:
        raise Rechazo("Poné un nombre para la cuenta", 400)

    tipo = _chequear_tipo_auxiliar(tipo_auxiliar, imputable)

    # El siguiente número libre entre las hijas del padre.
    existentes = db.execute(
        select(PlanCuenta.codigo).where(PlanCuenta.cuenta_padre_id == padre.id_cuenta)
    ).scalars().all()
    usados = set()
    for cod in existentes:
        ultimo = cod.rsplit(".", 1)[-1]
        if ultimo.isdigit():
            usados.add(int(ultimo))
    n = 1
    while n in usados:
        n += 1
    codigo = f"{padre.codigo}.{n:02d}"

    nueva = PlanCuenta(
        codigo=codigo,
        nombre=nombre,
        cuenta_padre_id=padre.id_cuenta,
        nivel=padre.nivel + 1,
        # La naturaleza sale del grupo de nivel 1; el lado, del mismo grupo
        # (o del nombre, en el 7). Una cuenta nueva nunca nace agrupadora.
        naturaleza=naturaleza_de(codigo),
        deudora_acreadora=deudora_de(codigo, nombre) if imputable else None,
        imputable=bool(imputable),
        tipo_auxiliar=tipo,
        activa=True,
    )
    db.add(nueva)
    db.commit()
    db.refresh(nueva)
    return obtener(db, nueva.id_cuenta)


def editar(
    db: Session,
    cuenta_id: int,
    nombre: str | None = None,
    imputable: bool | None = None,
    tipo_auxiliar: str | None = None,
    activa: bool | None = None,
) -> dict:
    """Cambia una cuenta. El código no se puede tocar."""
    c = db.get(PlanCuenta, cuenta_id)
    if c is None:
        raise Rechazo("La cuenta no existe", 404)

    cant_hijas = _hijas(db, cuenta_id)

    # --- nombre ---
    if nombre is not None:
        limpio = nombre.strip()
        if not limpio:
            raise Rechazo("El nombre no puede quedar vacío", 400)
        c.nombre = limpio

    # --- imputable ---
    if imputable is not None:
        if imputable and cant_hijas > 0:
            raise Rechazo(
                f"{c.codigo} {c.nombre} tiene {cant_hijas} subcuenta"
                f"{'s' if cant_hijas != 1 else ''}, así que es un agrupador y no "
                "puede ser imputable. Los movimientos van a las cuentas de abajo.",
                400,
            )
        c.imputable = bool(imputable)
        # El lado debe/haber sigue a la imputabilidad: si dejó de serlo, se va;
        # si pasó a serlo, se le calcula según su grupo.
        c.deudora_acreadora = (
            deudora_de(c.codigo, c.nombre) if imputable else None
        )

    # --- activa ---
    if activa is not None and not activa:
        if cant_hijas > 0:
            raise Rechazo(
                f"{c.codigo} {c.nombre} tiene {cant_hijas} subcuenta"
                f"{'s' if cant_hijas != 1 else ''}. Apagá primero las de abajo.",
                400,
            )
        c.activa = False

    # --- tipo_auxiliar ---
    # Depende de si quedó imputable, así que se mira después de arriba.
    if tipo_auxiliar is not None:
        c.tipo_auxiliar = _chequear_tipo_auxiliar(
            tipo_auxiliar, bool(c.imputable)
        )
    elif not c.imputable:
        # Si dejó de ser imputable, el tipo se va con ella.
        c.tipo_auxiliar = None

    db.commit()
    return obtener(db, cuenta_id)


def eliminar(db: Session, cuenta_id: int) -> None:
    """Apaga la cuenta. No la borra: si tiene subcuentas, no se puede."""
    c = db.get(PlanCuenta, cuenta_id)
    if c is None:
        raise Rechazo("La cuenta no existe", 404)

    cant_hijas = _hijas(db, cuenta_id)
    if cant_hijas > 0:
        raise Rechazo(
            f"{c.codigo} {c.nombre} tiene {cant_hijas} subcuenta"
            f"{'s' if cant_hijas != 1 else ''}: si se apaga, el árbol queda "
            "colgando. Apagá primero las de abajo.",
            409,
        )
    if not c.imputable:
        raise Rechazo(
            f"{c.codigo} {c.nombre} es un agrupador sin cuentas de detalle. "
            "Dejalo apagado con el botón, no se borra.",
            400,
        )

    c.activa = False
    db.commit()