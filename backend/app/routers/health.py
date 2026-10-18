"""Rutas de infraestructura: /health, sin datos de negocio y sin autenticación."""
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
        "model": (
            settings.openai_chat_model
            if settings.llm_provider == "openai"
            else settings.ollama_model
        ),
        "auth_provider": settings.auth_provider,
        "chunks_indexados": chunks,
    }
