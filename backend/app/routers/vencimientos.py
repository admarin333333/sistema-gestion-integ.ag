from fastapi import APIRouter, Body, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.usuario import Usuario
from app.services import vencimiento_service

router = APIRouter(prefix="/vencimientos-impositivos", tags=["vencimientos"])


# ---------------------------------------------------------------- conceptos

@router.get("/conceptos")
def listar_conceptos(
    incluir_inactivos: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Catálogo de conceptos: los de fábrica y los que hayas agregado."""
    return vencimiento_service.catalogo(db, solo_activos=not incluir_inactivos)


@router.post("/conceptos", status_code=status.HTTP_201_CREATED)
def crear_concepto(
    body: dict = Body(...),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Da de alta un concepto nuevo (por ejemplo 'Libro IVA Digital')."""
    return vencimiento_service.alta_concepto(
        db, nombre=body.get("nombre"), orden=body.get("orden")
    )


@router.put("/conceptos/{concepto_id}")
def editar_concepto(
    concepto_id: int,
    body: dict = Body(...),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Cambia el nombre, el orden o si el concepto está activo."""
    return vencimiento_service.editar_concepto(
        db,
        concepto_id,
        nombre=body.get("nombre"),
        orden=body.get("orden"),
        activo=body.get("activo"),
    )


@router.delete("/conceptos/{concepto_id}")
def desactivar_concepto(
    concepto_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Apaga un concepto. No borra los vencimientos que ya se cargaron con él."""
    return vencimiento_service.desactivar_concepto(db, concepto_id)


# ------------------------------------------------------------------- meses

@router.get("/meses")
def meses(
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Qué meses se han guardado y cuándo (para el árbol de Configuración)."""
    return vencimiento_service.meses_cargados(db)


@router.post("/meses/restaurar")
def restaurar(
    body: dict = Body(...),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Vuelve a poner el último guardado de un mes (desde el respaldo)."""
    return vencimiento_service.restaurar_mes(
        db, anio=int(body.get("anio")), mes=int(body.get("mes"))
    )


# -------------------------------------------------------------- vencimientos

@router.get("/impuestos")
def catalogo_impuestos(
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Los conceptos activos (los que aparecen en la grilla de Configuración)."""
    return [
        {"clave": c["clave"], "nombre": c["nombre"]}
        for c in vencimiento_service.catalogo(db, solo_activos=True)
    ]


@router.get("")
def listar(
    anio: int = Query(...),
    mes: int = Query(...),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Vencimientos cargados de un mes/año."""
    return vencimiento_service.listar(db, anio, mes)


@router.post("")
def guardar(
    anio: int = Query(...),
    mes: int = Query(...),
    filas: list[dict] = Body(...),
    vaciar: bool = Query(
        default=False, description="Confirmar que sí se vacíe el mes"
    ),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Reemplaza los vencimientos del mes/año por los que se mandan.

    Si el mes tenía datos y mandás la grilla vacía, responde 409 salvo que
    vengas con `vaciar=true`: así un clic sin querer no borra el mes.
    """
    return vencimiento_service.guardar_mes(
        db, anio, mes, filas, usuario=user.usuario, permitir_vacio=vaciar
    )


@router.get("/detalle")
def detalle(
    anio: int = Query(...),
    mes: int = Query(...),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Calendario del mes: vencimientos agrupados por dígito de CUIT + clientes."""
    return vencimiento_service.detalle_del_mes(db, anio, mes)