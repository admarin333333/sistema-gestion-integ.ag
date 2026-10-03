"""El catálogo de servicios que ofrece el ESTUDIO.

Los servicios ya se elegían al dar de alta un cliente (van en el POST de
`/api/clientes`), así que lo que faltaba era poder CARGAR uno nuevo sin tocar la
base a mano.

Tres reglas en el alta:

1. **El nombre no se repite.** La columna tiene UNIQUE, y hay que avisarlo con un
   mensaje que se entienda: si se dejara reventar, el contador vería un error de
   base de datos y no sabría qué hacer.
2. **El `orden` es el de aparición** en el formulario. Si no se pasa, se usa el
   último + 1, así el servicio nuevo queda al final y no desordena el resto.
3. **No se borra un servicio que tenga clientes.** Si un cliente lo tenía
   elegido y el servicio desaparece del catálogo, su ficha queda con algo que
   ya no existe.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_role
from app.core.errors import Rechazo
from app.database import get_db
from app.models.servicio import Servicio
from app.models.usuario import Usuario
from app.schemas.servicio import ServicioCrear, ServicioOut

router = APIRouter(prefix="/servicios", tags=["servicios"])


@router.get("", response_model=list[ServicioOut])
def listar(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return db.query(Servicio).order_by(Servicio.orden, Servicio.id).all()


@router.get("/{servicio_id}", response_model=ServicioOut)
def obtener(
    servicio_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    servicio = db.get(Servicio, servicio_id)
    if servicio is None:
        raise Rechazo("El servicio no existe", 404)
    return servicio


@router.post("", response_model=ServicioOut, status_code=status.HTTP_201_CREATED)
def crear(
    datos: ServicioCrear,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    """Carga un servicio nuevo. Solo el administrador.

    Es catálogo del estudio: si cualquiera lo modificara, un operador podría
    cambiarle el servicio a todos los clientes.
    """
    nombre = datos.nombre.strip()

    # Se busca antes de insertar para poder dar un error que se entienda. El
    # UNIQUE de la columna es la trava real (evita la carrera de dos altas con
    # el mismo nombre a la vez), pero sin esta consulta el error sería de la base.
    if db.query(Servicio).filter(func.lower(Servicio.nombre) == nombre.lower()).first():
        raise Rechazo(f"Ya existe un servicio llamado «{nombre}»", 409)

    # Sin `orden` explícito va al final: así el nuevo no desordena el formulario.
    orden = datos.orden
    if orden is None:
        ultimo = db.query(func.max(Servicio.orden)).scalar()
        orden = (ultimo or 0) + 1

    servicio = Servicio(nombre=nombre, orden=orden)
    db.add(servicio)
    try:
        db.commit()
    except IntegrityError:
        # Carrera: dos altas del mismo nombre al mismo tiempo. Saltó el UNIQUE.
        db.rollback()
        raise Rechazo(f"Ya existe un servicio llamado «{nombre}»", 409)
    db.refresh(servicio)
    return servicio


@router.delete("/{servicio_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(
    servicio_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_role("admin")),
):
    """Borra un servicio, pero SOLO si no tiene clientes.

    Con clientes no se borra: la ficha de esos clientes quedaría apuntando a un
    servicio que ya no existe, y no se vería por qué desapareció de la lista.
    """
    servicio = db.get(Servicio, servicio_id)
    if servicio is None:
        raise Rechazo("El servicio no existe", 404)

    cuantos = len(servicio.clientes)
    if cuantos:
        plural = "cliente tiene" if cuantos == 1 else "clientes tienen"
        raise Rechazo(
            f"No se puede borrar «{servicio.nombre}»: {cuantos} {plural} "
            "asignado. Si ya no se ofrece, dejalo cargado y no lo elijas en "
            "los clientes nuevos.",
            409,
        )

    db.delete(servicio)
    db.commit()
    return None