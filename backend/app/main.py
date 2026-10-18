"""Punto de entrada de la API de PonyArchive (FastAPI).

/api/auth/* no exige token previo (es el mecanismo para obtenerlo), /health es
infraestructura y el resto de /api/* exige Bearer token."""
from contextlib import asynccontextmanager
from threading import Thread

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import SessionLocal, init_db
from app.models import Document
from app.routers import auth, chat, documents, health, importer, library
from app.seed import seed_contexto, seed_if_empty

settings = get_settings()


def _sembrar() -> None:
    """Semilla e importación inicial en su propio hilo.

    En un despliegue nuevo la indexación con embeddings OpenAI tarda varios
    minutos: no puede bloquear el arranque ni el health check de la nube.
    """
    db = SessionLocal()
    try:
        result = seed_if_empty(db)
        print(f"[PonyArchive] Semilla: {result}")
        contexto = seed_contexto(db)
        if contexto.get("creadas"):
            print(f"[PonyArchive] Contexto del curso: {contexto}")
        if settings.import_on_start:
            from app.services.pony_api import (
                import_characters,
                import_episodes,
                import_songs,
            )

            hay_episodios = (
                db.query(Document).filter(Document.doc_type == "episodio").count() > 0
            )
            if hay_episodios:
                print(
                    "[PonyArchive] import_on_start: episodios ya presentes, se omite "
                    "la reimportación (usar POST /api/import/episodes para refrescar)."
                )
            else:
                episodios = import_episodes(db)
                personajes = import_characters(db)
                canciones = import_songs(db)
                print(
                    f"[PonyArchive] import_on_start: episodios={episodios}, "
                    f"personajes={personajes}, canciones={canciones}, "
                    f"documentos={db.query(Document).count()}"
                )
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    Thread(target=_sembrar, daemon=True).start()
    yield


app = FastAPI(
    title="PonyArchive API",
    version="0.1.0",
    description="Biblioteca inteligente de My Little Pony: Friendship Is Magic con agente RAG (LangChain + LangGraph).",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(health.router)
app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(chat.router, prefix=settings.api_prefix)
app.include_router(documents.router, prefix=settings.api_prefix)
app.include_router(library.router, prefix=settings.api_prefix)
app.include_router(importer.router, prefix=settings.api_prefix)
