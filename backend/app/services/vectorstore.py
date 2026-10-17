"""Base de datos vectorial (ChromaDB) con persistencia en disco.

Cada fragmento guarda metadatos para poder filtrar por:
  * doc_id      -> documento de origen (relación fragmento ↔ documento, §3.3)
  * doc_type    -> episodio | personaje | cancion | ficha_narrativa | upload
  * source      -> ponyapi | semilla | upload
  * continuity  -> "fim" (Friendship Is Magic)
  * title       -> título del documento
  * chunk_index -> posición del fragmento dentro del documento
"""
from threading import Lock

import chromadb

from app.config import get_settings

_client: chromadb.ClientAPI | None = None
_lock = Lock()


def get_collection():
    global _client
    with _lock:
        if _client is None:
            _client = chromadb.PersistentClient(path=get_settings().vector_dir)
    return _client.get_or_create_collection(
        name=get_settings().collection_name,
        metadata={"hnsw:space": "cosine"},
    )


def add_chunks(
    *,
    doc_id: int,
    texts: list[str],
    metadatas: list[dict],
    embeddings: list[list[float]],
) -> None:
    """Indexa los fragmentos de un documento. Los IDs son deterministas para
    poder reemplazar el documento sin duplicar fragmentos."""
    collection = get_collection()
    ids = [f"doc{doc_id}_chunk{i}" for i in range(len(texts))]
    collection.upsert(ids=ids, documents=texts, metadatas=metadatas, embeddings=embeddings)


def delete_document(doc_id: int) -> None:
    get_collection().delete(where={"doc_id": doc_id})


def search(
    query_embedding: list[float],
    *,
    k: int,
    doc_type: str | None = None,
    title_contains: str | None = None,
    theme: str | None = None,
    user_id: int | None = None,
    visible_to: int | None = None,
) -> list[dict]:
    """Busca los k fragmentos más similares, con filtros opcionales.

    Nota de implementación: Chroma 1.x no aplica `$contains` a cadenas
    multi-token (verificado el 2026-10-17 con 'trabajo en equipo' y
    'trabajo_en_equipo': 0 coincidencias pese a existir en los metadatos).
    Por eso `doc_type` y `title` se filtran en Chroma, y `theme` se filtra en
    Python sobre el conjunto recuperado, con ampliación previa de la búsqueda
    y respaldo sin filtro si el tema no coincide con nada.
    """
    collection = get_collection()
    clauses = []
    if doc_type:
        clauses.append({"doc_type": doc_type})
    if title_contains:
        clauses.append({"title": {"$contains": title_contains}})
    if user_id is not None:
        clauses.append({"user_id": user_id})   # documentos subidos por ese usuario
    if visible_to is not None:
        # Aislamiento de documentos: solo los compartidos (user_id=-1) y los propios
        clauses.append({"$or": [{"user_id": -1}, {"user_id": visible_to}]})
    if len(clauses) == 1:
        where = clauses[0]
    elif len(clauses) > 1:
        where = {"$and": clauses}
    else:
        where = None

    # Con filtro temático se piden más candidatos para poder descartarlos después
    n_results = k * 5 if theme else k

    try:
        result = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
    except Exception:
        # Chroma lanza error si el filtro no devuelve nada en algunas versiones
        return []

    out: list[dict] = []
    if not result or not result.get("documents"):
        return out
    for doc, meta, dist in zip(
        result["documents"][0], result["metadatas"][0], result["distances"][0]
    ):
        out.append({"text": doc, "score": 1.0 - float(dist), "metadata": meta})

    if theme:
        wanted = theme.strip().lower()
        with_theme = [
            r
            for r in out
            if wanted in [t.strip().lower() for t in r["metadata"].get("themes", "").split(",") if t.strip()]
        ]
        # Si el filtro temático no deja nada, se conserva la búsqueda general
        out = with_theme or out
    return out[:k]


def count_chunks() -> int:
    return get_collection().count()
