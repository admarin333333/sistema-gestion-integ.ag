from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.usuario import Usuario
from app.services import dashboard_service

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