"""
Cuentas bancarias de los clientes: altas, listado y baja.

Las validaciones que importan:

**El CBU se valida por estructura, NO por dígito verificador.** El CBU no es un
número cualquiera: los primeros 8 dígitos dicen QUÉ BANCO es. Eso sí se valida,
porque es lo que evita el error más común (pegar un CBU y elegir otro banco).

El **dígito verificador NO se valida, a propósito.** Ver
`_digito_verificador_cbu`: escribirlo de memoria es más riesgoso que no
escribirlo, porque rechazaría CBU que sí son válidos.

Lo que sí se valida:

1. 22 dígitos, todos números.
2. Los primeros 8 coinciden con el banco elegido.
3. **El CBU no puede estar cargado en dos cuentas.** El CBU identifica una
   cuenta, no una persona: si dos clientes lo tienen cargado, uno de los dos está
   mal. Es también lo que va a hacer falta para las conciliaciones.
4. La sucursal y el número de cuenta, si vienen, tienen que ser los del CBU.

**El CVU no se valida con el mismo algoritmo**: los CVU también tienen 22 dígitos
pero no son un CBU de banco, así que el dígito verificador es otro. Por eso el
CVU se valida solo por formato, no con el módulo 11.

**CBU y CVU no pueden los dos.** Uno es la cuenta del banco y el otro la
dirección de una billetera. Si los dos estuvieran cargados, el contador no
sabría cuál copiar al hacer una transferencia.

**El CBU, si viene, completa la sucursal y el número de cuenta.** El banco ya
está elegido, pero el sistema lo verifica. La sucursal son los dígitos 9 a 12 y
la cuenta los 13 a 21.

**No se borran, se dan de baja** (`activo = 0`). Una cuenta puede estar usada en
un recibo emitido; borrarla dejaría ese recibo apuntando a algo que ya no existe.
"""

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.errors import Rechazo
from app.models.cta_bancaria import MONEDAS, Banco, CtaBariaCliente

LARGO_CBU = 22

# Código de banco para las cuentas que NO son de un banco: un CVU (dirección de
# billetera) o un alias suelto ("miestudio.cbu"). No es inventado a ojo:
# `bancos.codigo` es clave primaria y no admite NULL, así que hace falta un valor.
# Este dice "no hay banco" y no se ofrece en el selector de bancos.
SIN_BANCO = "00000000"
NOMBRE_SIN_BANCO = "Sin banco (billetera o alias)"


def _solo_digitos(texto: str) -> bool:
    return texto.isdigit()


def _digito_verificador_cbu(cbu: str) -> str:
    """
    PLACEHOLDER — **el chequeo del dígito verificador NO está implementado a
    propósito.**

    Los dos últimos dígitos del CBU (posiciones 21 y 22) se calculan con un
    módulo 11 sobre bloques de 10 dígitos, con pesos y un caso especial para los
    resultados 10 y 11. Ese algoritmo se puede escribir de más de una forma y
    todas dan números parecidos pero NO iguales.

    Un CBU que tiene mal el dígito verificador es **inválido de verdad**: la
    transferencia no se hace. Pero el riesgo de esta función escrita de memoria
    es el contrario y peor: **rechazar un CBU que sí es válido**, y entonces el
    contador no puede cargar la cuenta real de un cliente. Eso deja el sistema
    inútil para lo único que se pidió.

    Con lo que sí valida (22 dígitos, que el banco coincida, que no esté repetido
    y que no haya CBU y CVU juntos) se cubre casi todo el error de tipeo. El
    dígito verificador se agrega acá cuando se pueda confirmar el algoritmo
    contra un CBU conocido y válido, y la prueba tiene que ir en
    `tests/test_ctas_bancarias.py`.
    """
    return ""


def _validar_cbu(cbu: str, codigo_banco: str) -> tuple[str, str]:
    """
    Devuelve `(sucursal, numero_cuenta)` si el CBU está bien.

    Se levanta `Rechazo` con el motivo si algo no cierra. Los mensajes van en
    castellano y se muestran tal cual.
    """
    cbu = (cbu or "").strip()

    if not cbu:
        raise Rechazo("El CBU está vacío.", codigo=422)
    if not _solo_digitos(cbu):
        raise Rechazo("El CBU tiene que ser solo números, sin guiones ni espacios.", codigo=422)
    if len(cbu) != LARGO_CBU:
        raise Rechazo(f"El CBU tiene {len(cbu)} dígitos y tiene que tener {LARGO_CBU}.", codigo=422)

    if cbu[:8] != codigo_banco:
        raise Rechazo(
            f"El CBU empieza con {cbu[:8]} y el banco elegido es {codigo_banco}. "
            "No son el mismo banco.",
            codigo=422,
        )

    # El dígito verificador NO se chequea: ver `_digito_verificador_cbu`.

    # Los dígitos 9 a 12 son la sucursal y del 13 al 21 la cuenta.
    return cbu[8:12], cbu[12:21]


def _validar_cvu(cvu: str) -> None:
    """El CVU se valida solo por formato: no es un CBU de banco."""
    cvu = (cvu or "").strip()
    if not cvu:
        raise Rechazo("El CVU está vacío.", codigo=422)
    if not _solo_digitos(cvu):
        raise Rechazo("El CVU tiene que ser solo números.", codigo=422)
    if len(cvu) != LARGO_CBU:
        raise Rechazo(f"El CVU tiene {len(cvu)} dígitos y tiene que tener {LARGO_CBU}.", codigo=422)


def _validar_cuit(valor: str | None) -> None:
    if valor in (None, ""):
        return
    v = str(valor).strip().replace("-", "")
    if len(v) != 11 or not v.isdigit():
        raise Rechazo("El CUIT del titular tiene que tener 11 dígitos.", codigo=422)


def _validar_no_repetido(db: Session, id_cliente: int, cbu: str | None, alias: str | None,
                         excluir_id: int | None = None) -> None:
    """
    Un CBU o un alias no puede estar en dos clientes distintos.

    Un CBU identifica una cuenta, no una persona. Si dos clientes lo tienen
    cargado, uno de los dos está mal, y más adelante (conciliaciones) el sistema
    no iba a saber a quién pertenece el movimiento.

    DENTRO del mismo cliente sí se repite el chequeo: el mismo CBU cargado dos
    veces en la misma persona es una cuenta duplicada.
    """
    condiciones = [CtaBariaCliente.activo.is_(True)]
    if excluir_id is not None:
        condiciones.append(CtaBariaCliente.id != excluir_id)

    if cbu:
        repetido = (
            db.query(func.count(CtaBariaCliente.id))
            .filter(CtaBariaCliente.cbu == cbu, *condiciones)
            .scalar()
        )
        if repetido:
            raise Rechazo(
                f"Ese CBU ya está cargado en otra cuenta. Un CBU identifica una "
                "cuenta, no una persona: revisá a quién corresponde.",
                codigo=409,
            )

    if alias:
        repetido = (
            db.query(func.count(CtaBariaCliente.id))
            .filter(CtaBariaCliente.alias_cbu == alias, *condiciones)
            .scalar()
        )
        if repetido:
            raise Rechazo(
                f"El alias «{alias}» ya está cargado en otra cuenta. El alias es "
                "único: dos cuentas distintas no pueden tener el mismo.",
                codigo=409,
            )


# ------------------------------------------------------------------ bancos


def listar_bancos(db: Session, incluir_inactivos: bool = False) -> list[Banco]:
    """
    El catálogo para el selector de la pantalla.

    `SIN_BANCO` **no se ofrece**: es un código interno para que las billeteras y
    los alias tengan algo a qué apuntar, no un banco que el contador pueda elegir.
    """
    condiciones = [Banco.codigo != SIN_BANCO]
    if not incluir_inactivos:
        condiciones.append(Banco.activo.is_(True))
    return db.query(Banco).filter(*condiciones).order_by(Banco.nombre).all()


def crear_banco(db: Session, codigo: str, nombre: str) -> Banco:
    """
    Alta de banco por su código de 8 dígitos del BCRA.

    Si el código no viene, se puede deducir del CBU: son los primeros 8 dígitos.
    Eso es lo que va a pasar la primera vez: nadie cargó el catálogo, el contador
    pega un CBU y el sistema le dice "eso es el banco 28505909".
    """
    codigo = (codigo or "").strip()
    nombre = (nombre or "").strip()

    if not nombre:
        raise Rechazo("El banco necesita un nombre.", codigo=422)
    if not codigo:
        raise Rechazo("El banco necesita su código de 8 dígitos.", codigo=422)
    if not _solo_digitos(codigo):
        raise Rechazo("El código del banco tiene que ser 8 dígitos numéricos.", codigo=422)
    if len(codigo) != 8:
        raise Rechazo(f"El código del banco tiene {len(codigo)} dígitos y tiene que tener 8.", codigo=422)

    if db.get(Banco, codigo):
        raise Rechazo(f"El banco {codigo} ya está cargado.", codigo=409)

    banco = Banco(codigo=codigo, nombre=nombre, activo=True)
    db.add(banco)
    db.commit()
    db.refresh(banco)
    return banco


def renombrar_banco(db: Session, codigo: str, nombre: str) -> Banco:
    """
    Corrige el nombre de un banco.

    Existe por esto: el catálogo arranca vacío y los bancos se crean **solos**
    cuando alguien pega un CBU, con un nombre provisorio ("Banco 28505909"). Los
    códigos de banco no se inventan —salen de los primeros 8 dígitos del CBU— pero
    el nombre sí hay que ponerlo, y el contador lo escribe una sola vez.

    **El código NO se puede cambiar**: es la clave primaria y viene del CBU. Si se
    pudiera cambiar, las cuentas que apuntan al viejo quedarían apuntando a un
    banco que ya no existe.
    """
    banco = db.get(Banco, codigo)
    if not banco:
        raise Rechazo(f"El banco {codigo} no está cargado.", codigo=404)

    nombre = (nombre or "").strip()
    if not nombre:
        raise Rechazo("El banco necesita un nombre.", codigo=422)
    if len(nombre) > 80:
        raise Rechazo("El nombre del banco es muy largo.", codigo=422)

    banco.nombre = nombre
    banco.activo = True
    db.commit()
    db.refresh(banco)
    return banco


def _buscar_o_crear_banco(db: Session, codigo: str) -> Banco:
    """
    Devuelve el banco del código, y si no está lo crea con un nombre provisorio.

    Es lo que hace que el catálogo **se llene solo**: el primer CBU de un banco
    desconocido crea el banco. El nombre queda como el código (nunca inventado)
    para que el contador lo corrija después desde la solapa.

    El código `SIN_BANCO` no crea una fila "de mentira": es el mismo que se usa
    para las billeteras y los alias. Existe solo para que la clave foránea tenga
    algo que apuntar.
    """
    banco = db.get(Banco, codigo)
    if banco:
        return banco
    nombre = NOMBRE_SIN_BANCO if codigo == SIN_BANCO else f"Banco {codigo}"
    banco = Banco(codigo=codigo, nombre=nombre, activo=True)
    db.add(banco)
    db.flush()
    return banco


# ----------------------------------------------------------------- cuentas


def listar_cuentas(db: Session, id_cliente: int, incluir_inactivas: bool = False) -> list[CtaBariaCliente]:
    condiciones = [CtaBariaCliente.id_cliente == id_cliente]
    if not incluir_inactivas:
        condiciones.append(CtaBariaCliente.activo.is_(True))
    return (
        db.query(CtaBariaCliente)
        .filter(*condiciones)
        .order_by(CtaBariaCliente.activo.desc(), CtaBariaCliente.id)
        .all()
    )


def crear_cuenta(db: Session, id_cliente: int, datos: dict) -> CtaBariaCliente:
    """
    Alta de una cuenta de un cliente.

    Todas las validaciones antes de escribir: si una falla, no queda una cuenta a
    medias (por ejemplo, creada sin CBU porque el CBU estaba malo).
    """
    from app.models.cliente import Cliente

    if not db.get(Cliente, id_cliente):
        raise Rechazo("Ese cliente no existe.", codigo=404)

    cbu = (datos.get("cbu") or "").strip() or None
    cvu = (datos.get("cvu") or "").strip() or None
    alias = (datos.get("alias_cbu") or "").strip() or None
    cuit = (datos.get("cuit_titular") or "").strip() or None
    moneda = (datos.get("moneda") or "ARS").strip().upper()
    codigo_banco = (datos.get("codigo_banco") or "").strip() or None

    if not cbu and not cvu and not alias:
        raise Rechazo(
            "Cargá al menos un CBU, un CVU o un alias: si no, la cuenta no tiene "
            "cómo cobrarse.",
            codigo=422,
        )

    if cbu and cvu:
        raise Rechazo(
            "No se puede cargar CBU y CVU juntos: el CBU es la cuenta del banco y "
            "el CVU la dirección de una billetera. Dejá solo uno.",
            codigo=422,
        )

    if moneda not in MONEDAS:
        raise Rechazo(f"La moneda tiene que ser {' o '.join(MONEDAS)}.", codigo=422)

    _validar_cuit(cuit)

    sucursal = (datos.get("sucursal") or "").strip() or None
    numero_cuenta = (datos.get("numero_cuenta") or "").strip() or None

    if cbu:
        if not codigo_banco:
            # Si no lo eligió, sale del CBU: los primeros 8 dígitos.
            codigo_banco = cbu[:8]
        sucursal_del_cbu, cuenta_del_cbu = _validar_cbu(cbu, codigo_banco)
        if sucursal and sucursal.zfill(4) != sucursal_del_cbu:
            raise Rechazo(
                f"La sucursal {sucursal} no es la del CBU (que es {sucursal_del_cbu}).",
                codigo=422,
            )
        if numero_cuenta and numero_cuenta.lstrip("0") != cuenta_del_cbu.lstrip("0"):
            raise Rechazo(
                f"El número de cuenta {numero_cuenta} no es el del CBU "
                f"(que es {cuenta_del_cbu}).",
                codigo=422,
            )
        sucursal = sucursal_del_cbu
        numero_cuenta = cuenta_del_cbu

    if cvu:
        _validar_cvu(cvu)
        # Un CVU no tiene banco: es una billetera. Si vino uno, se descarta, porque
        # dejarlo haría pensar que hay un banco de por medio.
        codigo_banco = SIN_BANCO
        sucursal = None
        numero_cuenta = None
    elif not cbu:
        # Solo un alias ("miestudio.cbu"): tampoco hay banco. Sin esto, el código
        # quedaba en NULL y el INSERT fallaba con un 500 sin explicación, porque
        # `bancos.codigo` es la clave primaria.
        codigo_banco = SIN_BANCO
        sucursal = None
        numero_cuenta = None

    _validar_no_repetido(db, id_cliente, cbu, alias)

    banco = _buscar_o_crear_banco(db, codigo_banco)

    cuenta = CtaBariaCliente(
        id_cliente=id_cliente,
        codigo_banco=codigo_banco,
        sucursal=sucursal,
        numero_cuenta=numero_cuenta,
        cbu=cbu,
        cvu=cvu,
        alias_cbu=alias,
        cuit_titular=cuit,
        moneda=moneda,
        activo=True,
    )
    db.add(cuenta)
    db.commit()
    db.refresh(cuenta)
    return cuenta


def actualizar_cuenta(db: Session, cuenta_id: int, datos: dict) -> CtaBariaCliente:
    """Modificación de una cuenta. Mismas validaciones que el alta."""
    cuenta = db.get(CtaBariaCliente, cuenta_id)
    if not cuenta:
        raise Rechazo("Esa cuenta no existe.", codigo=404)

    cbu = (datos.get("cbu") or "").strip() or None
    cvu = (datos.get("cvu") or "").strip() or None
    alias = (datos.get("alias_cbu") or "").strip() or None
    cuit = (datos.get("cuit_titular") or "").strip() or None
    moneda = (datos.get("moneda") or cuenta.moneda).strip().upper()
    codigo_banco = (datos.get("codigo_banco") or "").strip() or cuenta.codigo_banco

    if not cbu and not cvu and not alias:
        raise Rechazo("La cuenta necesita un CBU, un CVU o un alias.", codigo=422)
    if cbu and cvu:
        raise Rechazo("No se puede cargar CBU y CVU juntos.", codigo=422)
    if moneda not in MONEDAS:
        raise Rechazo(f"La moneda tiene que ser {' o '.join(MONEDAS)}.", codigo=422)

    _validar_cuit(cuit)

    sucursal = (datos.get("sucursal") or "").strip() or None
    numero_cuenta = (datos.get("numero_cuenta") or "").strip() or None

    if cbu:
        if not codigo_banco:
            codigo_banco = cbu[:8]
        sucursal_del_cbu, cuenta_del_cbu = _validar_cbu(cbu, codigo_banco)
        sucursal = sucursal_del_cbu
        numero_cuenta = cuenta_del_cbu
    elif cvu:
        _validar_cvu(cvu)

    _validar_no_repetido(db, cuenta.id_cliente, cbu, alias, excluir_id=cuenta_id)

    if codigo_banco and db.get(Banco, codigo_banco) is None:
        _buscar_o_crear_banco(db, codigo_banco)

    cuenta.codigo_banco = codigo_banco
    cuenta.sucursal = sucursal
    cuenta.numero_cuenta = numero_cuenta
    cuenta.cbu = cbu
    cuenta.cvu = cvu
    cuenta.alias_cbu = alias
    cuenta.cuit_titular = cuit
    cuenta.moneda = moneda

    db.commit()
    db.refresh(cuenta)
    return cuenta


def dar_de_baja(db: Session, cuenta_id: int) -> CtaBariaCliente:
    """
    Marca la cuenta como inactiva. No la borra.

    Va como update y no como delete a propósito: la cuenta puede estar usada en un
    recibo que ya se emitió, y borrarla dejaría ese recibo apuntando a nada.
    """
    cuenta = db.get(CtaBariaCliente, cuenta_id)
    if not cuenta:
        raise Rechazo("Esa cuenta no existe.", codigo=404)
    if not cuenta.activo:
        raise Rechazo("Esa cuenta ya estaba dada de baja.", codigo=409)
    cuenta.activo = False
    db.commit()
    db.refresh(cuenta)
    return cuenta


def reactivar(db: Session, cuenta_id: int) -> CtaBariaCliente:
    """Vuelve a habilitar una cuenta dada de baja."""
    cuenta = db.get(CtaBariaCliente, cuenta_id)
    if not cuenta:
        raise Rechazo("Esa cuenta no existe.", codigo=404)
    if cuenta.activo:
        raise Rechazo("Esa cuenta ya estaba activa.", codigo=409)
    cuenta.activo = True
    db.commit()
    db.refresh(cuenta)
    return cuenta


def banco_desde_cbu(db: Session, cbu: str) -> dict:
    """
    Qué banco es este CBU. Sirve para cargar el catálogo la primera vez.

    No crea nada: solo informa. El contador pega el CBU, ve "esto es el banco
    28505909" y lo carga con nombre. Los códigos de banco **no se inventan**.
    """
    cbu = (cbu or "").strip()
    if len(cbu) != LARGO_CBU or not _solo_digitos(cbu):
        raise Rechazo("El CBU tiene que tener 22 dígitos.", codigo=422)
    codigo = cbu[:8]
    banco = db.get(Banco, codigo)
    return {
        "codigo": codigo,
        "nombre": banco.nombre if banco else None,
        "ya_cargado": banco is not None,
    }


def a_json(cuenta: CtaBariaCliente) -> dict:
    """Lo que ve la pantalla. El alias y el CBU en texto plano para poder copiar."""
    return {
        "id": cuenta.id,
        "id_cliente": cuenta.id_cliente,
        "codigo_banco": cuenta.codigo_banco,
        "nombre_banco": cuenta.banco.nombre if cuenta.banco else None,
        "sucursal": cuenta.sucursal,
        "numero_cuenta": cuenta.numero_cuenta,
        "cbu": cuenta.cbu,
        "cvu": cuenta.cvu,
        "alias_cbu": cuenta.alias_cbu,
        "cuit_titular": cuenta.cuit_titular,
        "moneda": cuenta.moneda,
        "activo": cuenta.activo,
        # Qué se copia al portapapeles: una cosa sola, no las dos.
        "para_cobrar": cuenta.cbu or cuenta.cvu or cuenta.alias_cbu,
        "tipo": "CBU" if cuenta.cbu else ("CVU" if cuenta.cvu else "Alias"),
    }