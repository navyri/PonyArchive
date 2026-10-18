"""Importación del catálogo desde Pony API (endpoint de negocio protegido).

K03–K05: paginado, normalizado y sin duplicados. Cada registro guarda ID de
origen, procedencia, licencia y fecha de importación (creado por el modelo).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.security import get_current_user
from app.services.pony_api import import_characters, import_episodes, import_songs

router = APIRouter(prefix="/import", tags=["importación"])


@router.post("/episodes")
def trigger_episode_import(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        return import_episodes(db)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Pony API no disponible: {exc}")


@router.post("/characters")
def trigger_character_import(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        return import_characters(db)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Pony API no disponible: {exc}")


@router.post("/songs")
def trigger_song_import(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        return import_songs(db)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Pony API no disponible: {exc}")
