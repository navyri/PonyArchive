"""Seguridad: hash de contraseñas, emisión y validación de tokens.

Dos modos según AUTH_PROVIDER: "local" (JWT propio HS256 con usuarios en base
de datos) o "keycloak" (tokens verificados contra su JWKS)."""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import User

settings = get_settings()
bearer_scheme = HTTPBearer(auto_error=False)


# Contraseñas
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


# Tokens locales

def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "name": user.display_name,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_refresh_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=settings.refresh_token_expire_days),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


# Validación

def _decode_local(token: str) -> dict:
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])


def _decode_keycloak(token: str) -> dict:
    # Keycloak publica sus claves en /realms/{realm}/protocol/openid-connect/certs
    jwks_url = f"{settings.keycloak_url.rstrip('/')}/realms/{settings.keycloak_realm}/protocol/openid-connect/certs"
    issuer = f"{settings.keycloak_url.rstrip('/')}/realms/{settings.keycloak_realm}"
    jwk_client = PyJWKClient(jwks_url, cache_keys=True)
    signing_key = jwk_client.get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        issuer=issuer,
        audience=settings.keycloak_client_id,
        options={"verify_aud": True},
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Dependencia obligatoria de todo endpoint de negocio.

    Sin token válido -> 401. Con token de un usuario inexistente/inactivo -> 401.
    Ningún endpoint de negocio puede usar otra dependencia de autenticación.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticación requerida.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        payload = _decode_keycloak(token) if settings.auth_provider == "keycloak" else _decode_local(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expirado.")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido.")

    if payload.get("type") not in (None, "access"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Tipo de token no válido.")

    subject = payload.get("sub")
    email = payload.get("email") or ""

    user: User | None = None
    if subject and subject.isdigit():
        user = db.get(User, int(subject))
    if user is None and email:
        user = db.query(User).filter(User.email == email).first()

    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no autorizado.")
    return user
