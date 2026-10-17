"""Rutas de infraestructura: sin datos de negocio, sin autenticación.

Clasificación documentada en docs/matriz-requisitos.md §7: son comprobaciones de
salud para el despliegue y el orquestador, no endpoints de la aplicación.
"""
from fastapi import APIRouter

from app.config import get_settings
from app.services.vectorstore import count_chunks

router = APIRouter(tags=["infraestructura"])


@router.get("/health")
def health():
    settings = get_settings()
    try:
        chunks = count_chunks()
    except Exception:
        chunks = None
    return {
        "status": "ok",
        "app": settings.app_name,
        "env": settings.app_env,
        "model": settings.ollama_model,
        "auth_provider": settings.auth_provider,
        "chunks_indexados": chunks,
    }
