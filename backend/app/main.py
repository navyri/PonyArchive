"""Punto de entrada de la API de PonyArchive (FastAPI).

Clasificación de rutas (documentada en docs/matriz-requisitos.md §7):
  * /api/auth/*  -> obtención de credenciales (sin token previo por definición)
  * /health      -> infraestructura, sin datos de negocio
  * /api/*       -> NEGOCIO: todos estos routers exigen Bearer token mediante
                    la dependencia get_current_user de cada endpoint.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import SessionLocal, init_db
from app.routers import auth, chat, documents, health, importer, journal, library
from app.seed import seed_if_empty

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        result = seed_if_empty(db)
        print(f"[PonyArchive] Semilla: {result}")
    finally:
        db.close()
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
app.include_router(journal.router, prefix=settings.api_prefix)
app.include_router(importer.router, prefix=settings.api_prefix)
