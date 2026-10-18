"""Generación de embeddings con selección de proveedor.

Dos caminos según EMBEDDINGS_PROVIDER:

  "local"  sentence-transformers con intfloat/multilingual-e5-small (384 dims).
           e5 exige los prefijos "query: " y "passage: ", que se aplican aquí.
  "openai" API de embeddings de OpenAI (text-embedding-3-small, 1536 dims).

sentence_transformers se importa de forma perezosa dentro del camino local, de
modo que el proceso que usa OpenAI nunca carga torch.
"""
import math
from threading import Lock

import httpx

from app.config import get_settings

_model = None
_lock = Lock()


def _get_local_model():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer

                _model = SentenceTransformer(get_settings().embedding_model)
    return _model


def _embed_openai(texts: list[str], *, prefix: str) -> list[list[float]]:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError(
            "EMBEDDINGS_PROVIDER=openai pero OPENAI_API_KEY está vacía."
        )
    prefixed = [f"{prefix}{t.strip()}" for t in texts]
    resp = httpx.post(
        "https://api.openai.com/v1/embeddings",
        headers={"Authorization": f"Bearer {settings.openai_api_key}"},
        json={"model": settings.openai_embedding_model, "input": prefixed},
        timeout=60.0,
    )
    resp.raise_for_status()
    data = resp.json()["data"]
    data.sort(key=lambda d: d["index"])
    out: list[list[float]] = []
    for item in data:
        vec = item["embedding"]
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        out.append([v / norm for v in vec])
    return out


def embed_query(text: str) -> list[float]:
    settings = get_settings()
    if settings.embeddings_provider == "openai":
        return _embed_openai([text], prefix="query: ")[0]
    model = _get_local_model()
    return model.encode(f"query: {text.strip()}", normalize_embeddings=True).tolist()


def embed_passages(texts: list[str]) -> list[list[float]]:
    settings = get_settings()
    if settings.embeddings_provider == "openai":
        return _embed_openai(texts, prefix="passage: ")
    model = _get_local_model()
    return model.encode(
        [f"passage: {t.strip()}" for t in texts],
        normalize_embeddings=True,
        show_progress_bar=False,
    ).tolist()


def embedding_dims() -> int:
    settings = get_settings()
    if settings.embeddings_provider == "openai":
        return settings.openai_embedding_dims
    return 384
