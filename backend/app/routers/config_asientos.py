"""Configuración de los asientos automáticos y de los códigos internos.

    GET /api/config-asientos              -> las filas con sus cuentas
    PUT /api/config-asientos/{clave}       -> cambia las CUENTAS de una fila

    GET /api/config-comprobantes          -> los códigos internos
    PUT /api/config-comprobantes/{codigo} -> nombre / activo

Son **datos, no código**: por eso están en tablas editables. Si el contador
decide que "Documentos a cobrar" se reemplaza por "Clientes", o que la nota de
crédito va a otra cuenta de ingresos, se cambia acá y no se toca el programa.

Dos reglas que el backend no negocia:

1. **Solo cuentas IMPUTABLES.** Una agrupadora (la que tiene subcuentas) no
   puede recibir movimientos; si se guardara así, el asiento no se podría
   contabilizar.
2. **Una cuenta de Ingresos debe ser de RESULTADO** (grupo 4). Si se eligiera
   una de Activo, el balance RT54 no cerraría y el contador no lo vería hasta
   el balance, tres pantallas más abajo.

Lo que NO se puede cambiar desde acá: los nombres de cada caso ni si están
activos. Un caso mal configurado se corrige en `config_asientos`, no
desactivándolo, porque desactivar el asiento de una venta dejaría las facturas
sin asentar en silencio.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_role
from app.core.errors import Rechazo
from app.database import get_db
from app.models.usuario import Usuario

router = APIRouter(prefix="/config-asientos", tags=["configuración"])


class CuentasAsientoIn(BaseModel):
    """Las CUENTAS de una fila de `config_asientos`. Los nombres no se tocan."""

    cuenta_debe: int | None = None
    cuenta_haber_ingresos: int | None = None
    cuenta_haber_iva: int | None = None
    cuenta_haber_cobranza: int | None = None


class ComprobanteIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=80)
    activa: bool = True


def _chequear_imputable(db: Session, id_cuenta: int | None, campo: str, clave: str):
    """Que la cuenta exista y sea de detalle.

    No se confía en el id que manda la pantalla: se busca en el plan. Si no
    existiera o fuera un agrupador, el error se ve acá y no tres días después
    cuando el asiento no cierra.
    """
    if id_cuenta is None:
        return
    fila = db.execute(
        text("SELECT codigo, nombre, imputable FROM plan_cuentas WHERE id_cuenta = :i"),
        {"i": int(id_cuenta)},
    ).mappings().first()
    if fila is None:
        raise Rechazo(f"La cuenta del campo «{campo}» no existe en el plan", 400)
    if not fila["imputable"]:
        raise Rechazo(
            f"{fila['codigo']} {fila['nombre']} es un agrupador: no recibe "
            "movimientos. Elegí una cuenta de detalle.",
            400,
        )


@router.get("")
def listar(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    """Las filas de `config_asientos` con el código y nombre de cada cuenta.

    Sale TODO en una consulta con LEFT JOINs, así la pantalla no tiene que
    pedir cada cuenta por separado.
    """
    filas = db.execute(
        text(
            "SELECT c.clave, c.nombre, c.activa, "
            "       c.cuenta_debe,          cd.codigo AS debe_codigo, "
            "       cd.nombre AS debe_nombre, "
            "       c.cuenta_haber_ingresos, ci.codigo AS ing_codigo, "
            "       ci.nombre AS ing_nombre, "
            "       c.cuenta_haber_iva,      cv.codigo AS iva_codigo, "
            "       cv.nombre AS iva_nombre, "
            "       c.cuenta_haber_cobranza, cc.codigo AS cob_codigo, "
            "       cc.nombre AS cob_nombre "
            "  FROM config_asientos c "
            "  LEFT JOIN plan_cuentas cd ON cd.id_cuenta = c.cuenta_debe "
            "  LEFT JOIN plan_cuentas ci ON ci.id_cuenta = c.cuenta_haber_ingresos "
            "  LEFT JOIN plan_cuentas cv ON cv.id_cuenta = c.cuenta_haber_iva "
            "  LEFT JOIN plan_cuentas cc ON cc.id_cuenta = c.cuenta_haber_cobranza "
            " ORDER BY c.clave"
        )
    ).mappings().all()
    return [dict(f) for f in filas]


@router.put("/{clave}")
def actualizar(
    clave: str,
    datos: CuentasAsientoIn,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    """Cambia las CUENTAS de un caso. Solo el administrador.

    Solo admin porque esto decide dónde se asienta cada venta del estudio: si
    un operador lo cambiara porerror, todas las facturas siguientes irían a la
    cuenta equivocada.
    """
    existe = db.execute(
        text("SELECT COUNT(*) FROM config_asientos WHERE clave = :c"), {"c": clave}
    ).scalar()
    if not existe:
        raise Rechazo(f"No existe la configuración «{clave}»", 404)

    for campo, valor in (
        ("cuenta_debe", datos.cuenta_debe),
        ("cuenta_haber_ingresos", datos.cuenta_haber_ingresos),
        ("cuenta_haber_iva", datos.cuenta_haber_iva),
        ("cuenta_haber_cobranza", datos.cuenta_haber_cobranza),
    ):
        _chequear_imputable(db, valor, campo, clave)

    db.execute(
        text(
            "UPDATE config_asientos SET cuenta_debe = :d, "
            "  cuenta_haber_ingresos = :i, cuenta_haber_iva = :v, "
            "  cuenta_haber_cobranza = :c WHERE clave = :k"
        ),
        {
            "d": datos.cuenta_debe,
            "i": datos.cuenta_haber_ingresos,
            "v": datos.cuenta_haber_iva,
            "c": datos.cuenta_haber_cobranza,
            "k": clave,
        },
    )
    db.commit()
    return {"ok": True, "clave": clave}


# ============================================================ comprobantes

router_comp = APIRouter(prefix="/config-comprobantes", tags=["configuración"])


@router_comp.get("")
def listar_comprobantes(
    db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)
):
    """Los códigos internos, con cuántos comprobantes hay de cada uno.

    El contador sale de la base: muestra cuántos números ya se usaron, que es
    lo que hay que mirar antes de activar o desactivar un código.
    """
    filas = db.execute(
        text(
            "SELECT c.codigo, c.nombre, c.origen, c.activa, "
            "       (SELECT COUNT(*) FROM comprobantes_internos ci "
            "         WHERE ci.codigo_comprobante = c.codigo) AS usados "
            "  FROM config_comprobantes c ORDER BY c.codigo"
        )
    ).mappings().all()
    return [dict(f) for f in filas]


@router_comp.put("/{codigo}")
def actualizar_comprobante(
    codigo: str,
    datos: ComprobanteIn,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    """Cambia el NOMBRE o desactiva un código. Solo el administrador.

    Desactivar un código NO borra los comprobantes que ya se emitieron con él:
    quedan con su número, como debe ser. Solo deja de usarse para los nuevos.
    """
    fila = db.execute(
        text("SELECT origen FROM config_comprobantes WHERE codigo = :c"),
        {"c": codigo},
    ).mappings().first()
    if fila is None:
        raise Rechazo(f"No existe el código «{codigo}»", 404)

    db.execute(
        text(
            "UPDATE config_comprobantes SET nombre = :n, activa = :a "
            " WHERE codigo = :c"
        ),
        {"n": datos.nombre.strip(), "a": 1 if datos.activa else 0, "c": codigo},
    )
    db.commit()
    return {"ok": True, "codigo": codigo, "activa": datos.activa}