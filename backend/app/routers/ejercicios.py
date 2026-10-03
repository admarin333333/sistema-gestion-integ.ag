from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_role
from app.core.errors import Rechazo
from app.database import get_db
from app.models.usuario import Usuario
from app.services import ejercicio_service, periodo_service

router = APIRouter(prefix="/ejercicios", tags=["ejercicios"])


class EjercicioCrear(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=40)
    fecha_inicio: date
    fecha_fin: date
    cerrado: bool = False


class EjercicioEditar(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=40)
    fecha_inicio: date
    fecha_fin: date


class PeriodoOut(BaseModel):
    """Un período, como sale a la pantalla."""

    id_periodo: int
    id_ejercicio: int
    numero: int
    nombre: str
    fecha_inicio: date
    fecha_fin: date
    cerrado: bool
    cerrado_el: Optional[datetime] = None


@router.get("")
def listar(
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Los ejercicios del estudio, del más nuevo al más viejo."""
    return {
        "ejercicios": [ejercicio_service.a_json(e) for e in ejercicio_service.listar(db)],
        "resumen": _resumen(db),
    }


def _resumen(db: Session) -> dict:
    r = ejercicio_service.resumen(db)
    return {
        "cantidad": r["cantidad"],
        "abiertos": r["abiertos"],
        "cerrados": r["cerrados"],
        "vigente": ejercicio_service.a_json(r["vigente"]) if r["vigente"] else None,
    }


@router.get("/vigente")
def vigente(
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """El ejercicio abierto que contiene hoy: el que está trabajando el estudio.

    Lo pide la pantalla de Asientos para poner de título "Ejercicio 2026/2027".
    """
    e = ejercicio_service.vigente(db)
    return {
        "ejercicio": ejercicio_service.a_json(e) if e else None,
        "hoy": date.today(),
    }


# ------------------------------------------- períodos (los 12 meses)


@router.get("/periodos/{ejercicio_id}")
def listar_periodos(
    ejercicio_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Los 12 períodos del ejercicio con su estado y cuántos documentos tienen.

    Los `documentos` y `asientos` vienen en cada fila para que la pantalla muestre
    el aviso al cerrar sin tener que pedir un endpoint aparte.
    """
    e = ejercicio_service.obtener(db, ejercicio_id)
    periodos = periodo_service.listar(db, ejercicio_id)
    return {
        "ejercicio": ejercicio_service.a_json(e),
        "periodos": [periodo_service.a_json(p, db) for p in periodos],
    }


class PeriodoEstadoIn(BaseModel):
    cerrado: bool
    # El contador tiene que haber visto el aviso ("este período tiene 47
    # documentos") antes de cerrar. Sin este flag, `cambiar_estado` rebota y la
    # pantalla lo muestra y vuelve a mandar con `forzar=True`.
    forzar: bool = False


@router.post("/periodos/{periodo_id}/estado", response_model=PeriodoOut)
def cambiar_periodo(
    periodo_id: int,
    body: PeriodoEstadoIn,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    """Abre o cierra un período. Solo admin: es la decisión que frena la
    contabilidad."""
    return periodo_service.cambiar_estado(
        db, periodo_id, body.cerrado, user.id, forzar=body.forzar
    )


@router.get("/periodo-de-fecha")
def periodo_de_fecha(
    fecha: date = Query(..., description="Fecha a consultar"),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """En qué período cae una fecha, y si está abierto.

    Lo usa el selector de período de la Contabilidad para mostrar en cuál se está
    trabajando sin que la pantalla tenga que saber cómo se calculan los meses del
    ejercicio.
    """
    p = periodo_service.de_la_fecha(db, fecha)
    return {
        "periodo": periodo_service.a_json(p) if p else None,
        "ejercicio": (
            ejercicio_service.a_json(p.ejercicio) if p and p.ejercicio else None
        ),
    }


# ------------------------------------------- cuenta de cobro fija (cobranza)


class CuentaCobroIn(BaseModel):
    id_cuenta: int | None = Field(
        default=None,
        description="NULL = que cada recibo elija la suya",
    )


@router.get("/cuenta-cobro-fija")
def leer_cuenta_cobro(
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """En qué cuenta entra la plata de los recibos, por defecto.

    El contador dijo que es fondo fijo, así que se configura una vez y el
    recibo no lo pregunta. Cada recibo igual guarda la cuenta que usó.
    """
    from sqlalchemy import text

    from app.models.plan_cuenta import PlanCuenta

    valor = db.execute(
        text("SELECT valor FROM config_sistema WHERE clave = 'cuenta_cobro_fija'")
    ).scalar()
    cuenta = None
    if valor not in (None, ""):
        cuenta = db.get(PlanCuenta, int(valor))

    return {
        "id_cuenta": cuenta.id_cuenta if cuenta else None,
        "codigo": cuenta.codigo if cuenta else None,
        "nombre": cuenta.nombre if cuenta else None,
    }


@router.put("/cuenta-cobro-fija")
def guardar_cuenta_cobro(
    body: CuentaCobroIn,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    """Fija (o desfija) la cuenta de los recibos.

    No toca los recibos ya cargados: cada uno sigue con la cuenta que usó.
    """
    from datetime import datetime

    from sqlalchemy import text

    from app.core.errors import Rechazo
    from app.models.plan_cuenta import PlanCuenta

    valor = ""
    if body.id_cuenta is not None:
        cuenta = db.get(PlanCuenta, int(body.id_cuenta))
        if cuenta is None:
            raise Rechazo("La cuenta no existe", 400)
        if not cuenta.imputable:
            raise Rechazo(
                f"{cuenta.codigo} {cuenta.nombre} es un agrupador: elegí una "
                "cuenta de detalle.",
                400,
            )
        if not cuenta.activa:
            raise Rechazo(f"{cuenta.codigo} {cuenta.nombre} está apagada", 400)
        valor = str(cuenta.id_cuenta)

    db.execute(
        text(
            "INSERT INTO config_sistema (clave, valor, descripcion, actualizado) "
            "VALUES ('cuenta_cobro_fija', :v, "
            "        'Cuenta donde entra la plata de los recibos', NOW()) "
            "ON DUPLICATE KEY UPDATE valor = VALUES(valor), "
            "actualizado = VALUES(actualizado)"
        ),
        {"v": valor},
    )
    db.commit()

    return leer_cuenta_cobro(db=db, user=user)


@router.post("", status_code=201)
def crear(
    body: EjercicioCrear,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    e = ejercicio_service.crear(
        db, body.nombre, body.fecha_inicio, body.fecha_fin, body.cerrado
    )
    return ejercicio_service.a_json(e)


@router.put("/{ejercicio_id}")
def editar(
    ejercicio_id: int,
    body: EjercicioEditar,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    """Cambia nombre y fechas. Cerrar/abrir es otro endpoint."""
    e = ejercicio_service.editar(
        db, ejercicio_id, body.nombre, body.fecha_inicio, body.fecha_fin
    )
    return ejercicio_service.a_json(e)


@router.post("/{ejercicio_id}/cerrar")
def cerrar(
    ejercicio_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    """Cerrar = deja de recibir asientos.

    No exige que esté conciliado: es una trava para que nadie meta algo abajo de
    una fecha ya cerrada sin darse cuenta.
    """
    e = ejercicio_service.cambiar_estado(db, ejercicio_id, cerrado=True)
    return ejercicio_service.a_json(e)


@router.post("/{ejercicio_id}/abrir")
def abrir(
    ejercicio_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    """Reabrir un ejercicio cerrado. Avisa si se pisa con otro abierto."""
    e = ejercicio_service.cambiar_estado(db, ejercicio_id, cerrado=False)
    return ejercicio_service.a_json(e)