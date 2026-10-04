from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.usuario import Usuario
from app.schemas.cta_bancaria import (
    BancoDesdeCBUOut,
    BancoIn,
    BancoOut,
    CtaBancariaIn,
    CtaBancariaOut,
)
from app.services import cta_bancaria_service as servicio

router = APIRouter(prefix="/ctas-bancarias", tags=["cuentas bancarias"])


# ------------------------------------------------------------------ bancos


@router.get("/bancos", response_model=list[BancoOut])
def listar_bancos(
    incluir_inactivos: bool = False,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """El catálogo de bancos, por su código de 8 dígitos del BCRA."""
    return servicio.listar_bancos(db, incluir_inactivos=incluir_inactivos)


@router.post("/bancos", response_model=BancoOut, status_code=201)
def crear_banco(
    cuerpo: BancoIn,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """
    Alta de banco.

    También se puede crear **solo con el CBU**: el sistema crea el banco con el
    código que viene adentro, y el nombre queda como "Banco 28505909" para que el
    contador lo corrija. Los códigos de banco **no se inventan**: salen del CBU
    que pega el contador.
    """
    banco = servicio.crear_banco(db, cuerpo.codigo, cuerpo.nombre)
    return banco


@router.put("/bancos/{codigo}", response_model=BancoOut)
def renombrar_banco(
    codigo: str,
    cuerpo: BancoIn,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """
    Corrige el nombre de un banco.

    Es para los bancos que se crearon **solos** al pegar un CBU y quedaron con un
    nombre provisorio ("Banco 28505909"): el contador les pone el nombre una vez
    y listo.

    El código no se puede cambiar: es la clave primaria y sale del CBU.
    """
    banco = servicio.renombrar_banco(db, codigo, cuerpo.nombre)
    return banco


@router.get("/bancos/desde-cbu", response_model=BancoDesdeCBUOut)
def banco_desde_cbu(
    cbu: str,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """
    Qué banco es este CBU. Sirve para cargar el catálogo la primera vez: se pega
    el CBU de un cliente y el sistema dice a qué banco pertenece.
    """
    return servicio.banco_desde_cbu(db, cbu)


# ----------------------------------------------------------------- cuentas


@router.get("/clientes/{cliente_id}", response_model=list[CtaBancariaOut])
def listar_cuentas(
    cliente_id: int,
    incluir_inactivas: bool = False,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Las cuentas de UN cliente. Un cliente puede tener varias."""
    return [servicio.a_json(c) for c in servicio.listar_cuentas(db, cliente_id, incluir_inactivas)]


@router.post("/clientes/{cliente_id}", response_model=CtaBancariaOut, status_code=201)
def crear_cuenta(
    cliente_id: int,
    cuerpo: CtaBancariaIn,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """
    Alta de una cuenta bancaria del cliente.

    El CBU completa solo la sucursal y el número de cuenta, y verifica que el
    banco coincida con los primeros 8 dígitos.
    """
    cuenta = servicio.crear_cuenta(db, cliente_id, cuerpo.model_dump())
    return servicio.a_json(cuenta)


@router.put("/{cuenta_id}", response_model=CtaBancariaOut)
def actualizar_cuenta(
    cuenta_id: int,
    cuerpo: CtaBancariaIn,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Modificación de una cuenta."""
    cuenta = servicio.actualizar_cuenta(db, cuenta_id, cuerpo.model_dump())
    return servicio.a_json(cuenta)


@router.post("/{cuenta_id}/baja", response_model=CtaBancariaOut)
def dar_de_baja(
    cuenta_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """
    Da de baja la cuenta: la esconde pero no la borra.

    No se borra porque puede estar usada en un recibo que ya se emitió, y borrar
    dejaría ese recibo apuntando a una cuenta que ya no existe.
    """
    cuenta = servicio.dar_de_baja(db, cuenta_id)
    return servicio.a_json(cuenta)


@router.post("/{cuenta_id}/reactivar", response_model=CtaBancariaOut)
def reactivar(
    cuenta_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Vuelve a habilitar una cuenta dada de baja."""
    cuenta = servicio.reactivar(db, cuenta_id)
    return servicio.a_json(cuenta)