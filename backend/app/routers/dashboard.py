from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.usuario import Usuario
from app.services import dashboard_service, ejercicio_service, informes_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/kpis")
def get_kpis(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """KPIs del dashboard."""
    return dashboard_service.kpis(db)


@router.get("/alertas")
def get_alertas(
    dias: int = 30,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Alertas de vencimiento (facturas vencidas y por vencer)."""
    return dashboard_service.alertas_vencimiento(db, limite_dias=dias)


@router.get("/proximas-vencimientos")
def get_proximas_vencimientos(
    dias: int = 7,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Facturas que vencen en los próximos N días."""
    return dashboard_service.facturas_por_vencer(db, dias=dias)


@router.get("/resultado-por-periodo")
def resultado_por_periodo(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Ingresos y gastos de los 12 meses del ejercicio vigente, para el gráfico.

    Sin parámetro de ejercicio a propósito: el gráfico es "cómo va el año", y el
    año que corre es el vigente. Si no hay ejercicio vigente contesta 409 con el
    motivo, para que la pantalla pueda decirlo y no inventar un gráfico vacío.
    """
    ejercicio = ejercicio_service.vigente(db)
    if not ejercicio:
        from app.core.errors import Rechazo
        raise Rechazo(
            "No hay ningun ejercicio vigente. Crea el ejercicio en "
            "Configuracion para ver el gr��fico de ingresos y gastos.",
            codigo=409,
        )
    return informes_service.resultado_por_periodo(db, ejercicio.id_ejercicio)