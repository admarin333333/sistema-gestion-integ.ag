from sqlalchemy.orm import Session

from app.core.security import create_token, verify_password
from app.models.usuario import Usuario


def authenticate(db: Session, usuario: str, password: str) -> Usuario | None:
    user = db.query(Usuario).filter(Usuario.usuario == usuario).first()
    if user is None or not user.activo:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def login(db: Session, usuario: str, password: str) -> str | None:
    user = authenticate(db, usuario, password)
    if user is None:
        return None
    return create_token(user.id, user.rol)
