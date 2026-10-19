"""Endpoints de autenticación.

Rutas sin token previo por definición: son el mecanismo para obtenerlo. Se
protegen con HTTPS, validación de entrada, hashing bcrypt y limitación de
intentos. El resto de la API exige Bearer token."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import User
from app.security import (
    create_access_token,
    create_refresh_token,
    get_current_user,
    get_instance_id,
    hash_password,
    verify_password,
)
import jwt

router = APIRouter(prefix="/auth", tags=["autenticación"])
settings = get_settings()


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    display_name: str = Field(default="", max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict


def _user_payload(user: User) -> dict:
    return {"id": user.id, "email": user.email, "display_name": user.display_name}


def _tokens(user: User, db: Session) -> TokenResponse:
    instance_id = get_instance_id(db)
    return TokenResponse(
        access_token=create_access_token(user, instance_id),
        refresh_token=create_refresh_token(user, instance_id),
        user=_user_payload(user),
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    if settings.auth_provider == "keycloak":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Con AUTH_PROVIDER=keycloak el registro se realiza en la consola de Keycloak.",
        )
    if db.query(User).filter(User.email == payload.email.lower()).first():
        raise HTTPException(status_code=409, detail="Ese correo ya está registrado.")
    user = User(
        email=payload.email.lower(),
        display_name=payload.display_name or payload.email.split("@")[0],
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _tokens(user, db)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Usuario desactivado.")
    return _tokens(user, db)


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    try:
        data = jwt.decode(
            payload.refresh_token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expirado.")
    except Exception:
        raise HTTPException(status_code=401, detail="Refresh token inválido.")

    if data.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Tipo de token no válido.")

    # Misma salvaguarda que en el access token: un refresh de una BD anterior
    # no debe poder mintir tokens para los ids (reasignados) de la BD actual.
    if data.get("inst") != get_instance_id(db):
        raise HTTPException(status_code=401, detail="Refresh caducado. Vuelve a iniciar sesión.")

    user = db.get(User, int(data["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Usuario no autorizado.")
    return _tokens(user, db)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout():
    """Los JWT son stateless: el cliente descarta el token."""
    return None


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return _user_payload(user)
