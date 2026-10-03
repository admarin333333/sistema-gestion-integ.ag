"""Vencimientos impositivos: catálogo de conceptos y grilla de cada mes.

El catálogo de conceptos vive en `conceptos_vencimiento` (se edita desde
Configuración) y los vencimientos de cada mes en `vencimientos_impositivos`.
Un mes se guarda entero: al guardar se borra lo que había de ese mes y se
ponen las filas nuevas, así que los otros meses no se tocan.
"""

import re
import unicodedata
from datetime import date, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.errors import Rechazo
from app.models.cliente import Cliente
from app.models.concepto_vencimiento import ConceptoVencimiento
from app.models.persona import Persona
from app.models.vencimiento_impositivo import VencimientoImpositivo
from app.models.vencimiento_mes import VencimientoMes

MESES = (
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
)


def _validar_periodo(anio: int, mes: int) -> None:
    if not (2000 <= anio <= 2100):
        raise Rechazo("El año está fuera de rango", 400)
    if not (1 <= mes <= 12):
        raise Rechazo("El mes debe estar entre 1 y 12", 400)


# --------------------------------------------------------------- conceptos

def _clave_desde_nombre(nombre: str) -> str:
    """'Libro IVA Digital' -> 'libro_iva_digital'."""
    normal = unicodedata.normalize("NFKD", nombre)
    sin_acentos = "".join(c for c in normal if not unicodedata.combining(c))
    limpio = re.sub(r"[^a-zA-Z0-9]+", "_", sin_acentos).strip("_").lower()
    return limpio or "concepto"


def catalogo(db: Session, solo_activos: bool = True) -> list[dict]:
    """Los conceptos de vencimiento, en el orden en que aparecen en la grilla."""
    consulta = select(ConceptoVencimiento)
    if solo_activos:
        consulta = consulta.where(ConceptoVencimiento.activo.is_(True))
    filas = (
        db.execute(
            consulta.order_by(ConceptoVencimiento.orden, ConceptoVencimiento.nombre)
        )
        .scalars()
        .all()
    )
    return [_a_json_concepto(f) for f in filas]


def _a_json_concepto(f: ConceptoVencimiento) -> dict:
    return {
        "id": f.id,
        "clave": f.clave,
        "nombre": f.nombre,
        "orden": f.orden,
        "sistema": f.sistema,
        "activo": f.activo,
    }


def _nombres(db: Session) -> dict[str, str]:
    """Mapa clave -> nombre de **todos** los conceptos (activos o no).

    Se usan los inactivos también, para que los vencimientos ya cargados de un
    concepto apagado sigan mostrando su nombre y no la clave fea.
    """
    filas = db.execute(select(ConceptoVencimiento)).scalars().all()
    return {f.clave: f.nombre for f in filas}


def alta_concepto(db: Session, nombre: str, orden: int | None = None) -> dict:
    """Da de alta un concepto nuevo (p.ej. 'Libro IVA Digital')."""
    nombre = (nombre or "").strip()
    if not nombre:
        raise Rechazo("Poné un nombre para el concepto", 400)
    if len(nombre) > 80:
        raise Rechazo("El nombre del concepto es muy largo (máximo 80)", 400)

    repetido = db.execute(
        select(ConceptoVencimiento).where(
            func.lower(ConceptoVencimiento.nombre) == nombre.lower()
        )
    ).scalars().first()
    if repetido:
        if not repetido.activo:
            # Si está apagado no alcanza con crear otro: hay que volver a
            # encender ése, o si no quedan dos columnas iguales en la grilla.
            raise Rechazo(
                f"«{nombre}» ya existe pero está apagado. Volvé a encenderlo en el "
                "catálogo en vez de agregarlo de nuevo.",
                409,
            )
        raise Rechazo(f"Ya existe un concepto que se llama «{nombre}»", 409)

    base = _clave_desde_nombre(nombre)
    clave = base
    n = 2
    while db.execute(
        select(ConceptoVencimiento).where(ConceptoVencimiento.clave == clave)
    ).first():
        clave = f"{base}_{n}"
        n += 1

    if orden is None:
        ultimo = db.execute(
            select(func.max(ConceptoVencimiento.orden))
        ).scalar()
        orden = int(ultimo or 0) + 1

    nuevo = ConceptoVencimiento(
        clave=clave,
        nombre=nombre,
        orden=orden,
        sistema=False,
        activo=True,
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return _a_json_concepto(nuevo)


def editar_concepto(
    db: Session,
    concepto_id: int,
    nombre: str | None = None,
    orden: int | None = None,
    activo: bool | None = None,
) -> dict:
    """Cambia el nombre, el lugar o si el concepto está activo."""
    concepto = db.get(ConceptoVencimiento, concepto_id)
    if concepto is None:
        raise Rechazo("No existe ese concepto", 404)

    if nombre is not None:
        nombre = nombre.strip()
        if not nombre:
            raise Rechazo("El nombre no puede quedar vacío", 400)
        otro = db.execute(
            select(ConceptoVencimiento).where(
                func.lower(ConceptoVencimiento.nombre) == nombre.lower(),
                ConceptoVencimiento.id != concepto_id,
            )
        ).first()
        if otro:
            raise Rechazo(f"Ya existe un concepto que se llama «{nombre}»", 409)
        concepto.nombre = nombre

    if orden is not None:
        concepto.orden = int(orden)
    if activo is not None:
        concepto.activo = bool(activo)

    concepto.actualizado = datetime.utcnow()
    db.commit()
    db.refresh(concepto)
    return _a_json_concepto(concepto)


def desactivar_concepto(db: Session, concepto_id: int) -> dict:
    """Apaga un concepto (deja de aparecer en la grilla nueva).

    **No borra nada**: los vencimientos que ya estaban cargados con ese concepto
    se siguen viendo en la pantalla de consulta con su nombre.
    """
    concepto = db.get(ConceptoVencimiento, concepto_id)
    if concepto is None:
        raise Rechazo("No existe ese concepto", 404)
    concepto.activo = False
    concepto.actualizado = datetime.utcnow()
    db.commit()
    db.refresh(concepto)
    return _a_json_concepto(concepto)


# ------------------------------------------------------- grilla por mes

def meses_cargados(db: Session) -> list[dict]:
    """Qué meses se han guardado, para armar el árbol de Configuración.

    Sale de `vencimientos_meses` (un registro por mes), así que un mes que
    quedó vacío también aparece, con su fecha de última actualización.
    """
    filas = (
        db.execute(
            select(VencimientoMes)
            .order_by(VencimientoMes.anio.desc(), VencimientoMes.mes.desc())
        )
        .scalars()
        .all()
    )
    return [
        {
            "anio": f.anio,
            "mes": f.mes,
            "cantidad": f.cantidad,
            "ultimo_cambio": f.ultimo_cambio.isoformat(),
            "usuario": f.usuario,
            # Si el mes quedó vacío pero hubo un guardado anterior, se puede
            # recuperar el respaldo.
            "tiene_respaldo": bool(f.respaldo),
        }
        for f in filas
    ]


def _registrar_mes(
    db: Session, anio: int, mes: int, filas: list[dict], usuario: str | None
) -> None:
    """Deja el registro del mes: cuándo se guardó, cuánto hay y un respaldo."""
    import json

    respaldo = json.dumps(
        [
            {
                "ultimo_digito": f["ultimo_digito"],
                "impuesto": f["impuesto"],
                "fecha_vencimiento": f["fecha_vencimiento"],
            }
            for f in filas
        ]
    )
    registro = (
        db.execute(
            select(VencimientoMes).where(
                VencimientoMes.anio == anio, VencimientoMes.mes == mes
            )
        )
        .scalars()
        .first()
    )
    if registro is None:
        db.add(
            VencimientoMes(
                anio=anio,
                mes=mes,
                cantidad=len(filas),
                ultimo_cambio=datetime.utcnow(),
                usuario=usuario,
                respaldo=respaldo,
            )
        )
    else:
        registro.cantidad = len(filas)
        registro.ultimo_cambio = datetime.utcnow()
        registro.usuario = usuario
        registro.respaldo = respaldo


def restaurar_mes(db: Session, anio: int, mes: int) -> dict:
    """Vuelve a poner el último guardado que quedó en el respaldo."""
    _validar_periodo(anio, mes)
    registro = (
        db.execute(
            select(VencimientoMes).where(
                VencimientoMes.anio == anio, VencimientoMes.mes == mes
            )
        )
        .scalars()
        .first()
    )
    if registro is None or not registro.respaldo:
        raise Rechazo("No hay ningún respaldo guardado de ese mes", 404)

    import json

    filas = json.loads(registro.respaldo)
    guardar_mes(db, anio, mes, filas, usuario="restauracion", permitir_vacio=True)
    return {"restaurados": len(filas), "anio": anio, "mes": mes}


def listar(db: Session, anio: int, mes: int) -> list[dict]:
    """Los vencimientos cargados de ese mes/año, ordenados por dígito e impuesto."""
    _validar_periodo(anio, mes)
    nombres = _nombres(db)
    filas = (
        db.execute(
            select(VencimientoImpositivo)
            .where(VencimientoImpositivo.anio == anio, VencimientoImpositivo.mes == mes)
            .order_by(
                VencimientoImpositivo.ultimo_digito, VencimientoImpositivo.fecha_vencimiento
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": f.id,
            "ultimo_digito": f.ultimo_digito,
            "impuesto": f.impuesto,
            "impuesto_label": nombres.get(f.impuesto, f.impuesto),
            "fecha_vencimiento": f.fecha_vencimiento.isoformat(),
        }
        for f in filas
    ]


def guardar_mes(
    db: Session,
    anio: int,
    mes: int,
    filas: list[dict],
    usuario: str | None = None,
    permitir_vacio: bool = False,
) -> dict:
    """Reemplaza los vencimientos del mes/año por los que se mandan.

    Cada fila es {ultimo_digito, impuesto, fecha_vencimiento}. Se ignora lo que
    venga vacío, así se puede mandar la grilla completa con huecos.

    **Solo toca este mes**: los demás quedan como están.

    Ojo con el borrado: si el mes ya tenía datos y mandás la grilla vacía, el
    sistema se niega salvo que venga `permitir_vacio`. Sin eso, un clic sin
    querer (o una grilla que no cargó) vaciaría el mes entero. Y antes de
    borrar queda un **respaldo** en `vencimientos_meses`, por si acaso.
    """
    _validar_periodo(anio, mes)
    validos = {c["clave"] for c in catalogo(db, solo_activos=True)}

    # Validar TODO antes de borrar nada.
    limpias: list[dict] = []
    for f in filas:
        digito = f.get("ultimo_digito")
        impuesto = (f.get("impuesto") or "").strip()
        fecha = f.get("fecha_vencimiento")
        if digito is None or digito == "" or not impuesto or not fecha:
            continue
        digito = int(digito)
        if not (0 <= digito <= 9):
            raise Rechazo(f"El dígito {digito} no es válido (tiene que ser 0 a 9)", 400)
        if impuesto not in validos:
            raise Rechazo(f"Concepto desconocido: {impuesto}", 400)
        fecha_v = fecha if isinstance(fecha, date) else date.fromisoformat(str(fecha))
        limpias.append(
            {
                "ultimo_digito": digito,
                "impuesto": impuesto,
                "fecha_vencimiento": fecha_v.isoformat(),
            }
        )

    # traversed: si hay datos y mandás vacío, no se borra nada sin permiso.
    ya_habia = db.execute(
        select(func.count(VencimientoImpositivo.id)).where(
            VencimientoImpositivo.anio == anio, VencimientoImpositivo.mes == mes
        )
    ).scalar()
    if ya_habia and not limpias and not permitir_vacio:
        raise Rechazo(
            f"{MESES[mes - 1]} {anio} tiene {ya_habia} vencimientos cargados. "
            "Si querés vaciar el mes, confirmalo abajo "
            "(queda un respaldo por si te arrepentís).",
            409,
        )

    db.execute(
        delete(VencimientoImpositivo).where(
            VencimientoImpositivo.anio == anio, VencimientoImpositivo.mes == mes
        )
    )
    for f in limpias:
        db.add(
            VencimientoImpositivo(
                anio=anio,
                mes=mes,
                ultimo_digito=f["ultimo_digito"],
                impuesto=f["impuesto"],
                fecha_vencimiento=date.fromisoformat(f["fecha_vencimiento"]),
            )
        )

    # Registro del mes con su respaldo (antes del commit: va en la misma
    # transacción, así que si algo falla no queda nada a medias).
    _registrar_mes(db, anio, mes, limpias, usuario)

    db.commit()
    return {
        "guardadas": len(limpias),
        "anio": anio,
        "mes": mes,
        "ultimo_cambio": datetime.utcnow().isoformat(),
    }


def detalle_del_mes(db: Session, anio: int, mes: int) -> dict:
    """Calendario del mes: qué vence a cada dígito de CUIT, y a quién le toca.

    Une dos cosas:
    - lo cargado en la grilla (`listar`), agrupado por último dígito;
    - los clientes del estudio agrupados por su último dígito (`clientes_por_digito`),
      para poder avisarle a cada uno.

    Los clientes sin CUIT van aparte en `sin_cuit`: no tienen dígito, así que
    no pueden entrar en la grilla y hay que informarlos por separado.
    """
    _validar_periodo(anio, mes)

    # 1. Los vencimientos del mes, agrupados por dígito.
    por_digito: dict[int, list[dict]] = {}
    for f in listar(db, anio, mes):
        por_digito.setdefault(f["ultimo_digito"], []).append(
            {
                "impuesto": f["impuesto"],
                "impuesto_label": f["impuesto_label"],
                "fecha_vencimiento": f["fecha_vencimiento"],
            }
        )

    grupos = []
    for digito in sorted(por_digito):
        vencimientos = por_digito[digito]
        # La fecha que "manda" para ese dígito es la más próxima: es la que
        # hay que tener en cuenta para avisarle al cliente.
        fechas = [date.fromisoformat(v["fecha_vencimiento"]) for v in vencimientos]
        grupos.append(
            {
                "ultimo_digito": digito,
                "items": vencimientos,
                "primera_fecha": min(fechas).isoformat(),
                "ultima_fecha": max(fechas).isoformat(),
            }
        )

    # 2. Los clientes, para saber a quién le corresponde cada grupo.
    clientes = clientes_por_digito(db)
    for g in grupos:
        g["clientes"] = clientes["grupos"].get(g["ultimo_digito"], [])
        g["cantidad_clientes"] = len(g["clientes"])

    return {
        "anio": anio,
        "mes": mes,
        "grupos": grupos,
        "sin_cuit": clientes["sin_cuit"],
        "total_vencimientos": sum(len(g["items"]) for g in grupos),
        "total_clientes": sum(len(v) for v in clientes["grupos"].values()),
    }


def clientes_por_digito(db: Session) -> dict:
    """Agrupa los clientes por el último dígito de su CUIT.

    Los que no tienen CUIT van aparte en `sin_cuit` para poder informarlos.
    """
    filas = (
        db.execute(
            select(Persona.nombre, Persona.apellido, Persona.cuit, Persona.dni)
            .join(Cliente, Cliente.persona_id == Persona.id)
            .order_by(Cliente.nro_cuenta)
        )
        .all()
    )
    grupos: dict[int, list[dict]] = {}
    sin_cuit: list[dict] = []
    for nombre, apellido, cuit, dni in filas:
        nombre_completo = (
            nombre if (apellido is None) else f"{apellido}, {nombre}"
        )
        if not cuit:
            sin_cuit.append({"nombre": nombre_completo, "cuit": None, "dni": dni})
            continue
        digito = int(str(cuit)[-1])
        grupos.setdefault(digito, []).append(
            {"nombre": nombre_completo, "cuit": cuit}
        )
    return {"grupos": grupos, "sin_cuit": sin_cuit}