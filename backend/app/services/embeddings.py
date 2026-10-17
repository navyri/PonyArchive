"""Embeddings locales con sentence-transformers (multilingüe para español).

DEC-09: intfloat/multilingual-e5-small (384 dimensiones). Verificado el
2026-10-17: similitud 0,899 entre una pregunta y su pasaje relevante.
e5 exige los prefijos "query: " y "passage: ", que se aplican aquí para que
la búsqueda no degenere.
"""
from threading import Lock

from sentence_transformers import SentenceTransformer

from app.config import get_settings

_model: SentenceTransformer | None = None
_lock = Lock()


def get_embedding_model() -> SentenceTransformer:
    global _model
    with _lock:
        if _model is None:
            _model = SentenceTransformer(get_settings().embedding_model)
    return _model


def embed_query(text: str) -> list[float]:
    model = get_embedding_model()
    return model.encode(f"query: {text.strip()}", normalize_embeddings=True).tolist()


def embed_passages(texts: list[str]) -> list[list[float]]:
    model = get_embedding_model()
    return model.encode(
        [f"passage: {t.strip()}" for t in texts],
        normalize_embeddings=True,
        show_progress_bar=False,
    ).tolist()
