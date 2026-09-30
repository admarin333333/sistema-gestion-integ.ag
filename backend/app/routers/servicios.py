from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.servicio import Servicio
from app.models.usuario import Usuario
from app.schemas.servicio import ServicioOut

router = APIRouter(prefix="/servicios", tags=["servicios"])


@router.get("", response_model=list[ServicioOut])
def listar(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return db.query(Servicio).order_by(Servicio.orden, Servicio.id).all()
