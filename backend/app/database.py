"""Conexión y sesión de la base de datos relacional (SQLite con SQLAlchemy)."""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings

settings = get_settings()

# check_same_thread solo existe en SQLite. Si la URL apunta a un motor distinto
# (p. ej. Postgres gestionado en la nube), pasar ese argumento rompería el
# arranque, así que se aplica condicionalmente.
_SQLITE = settings.database_url.startswith("sqlite")

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if _SQLITE else {},
    pool_pre_ping=True,  # reconexión limpia tras inactividad (p. ej. Postgres serverless)
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db():
    """Dependencia de FastAPI: una sesión por petición."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Crea las tablas si no existen. Se llama al arrancar la aplicación."""
    from app import models  # noqa: F401  (registro de modelos)

    Base.metadata.create_all(bind=engine)
