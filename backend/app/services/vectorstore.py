"""Base de datos vectorial con selección de proveedor.

Dos backends según VECTOR_PROVIDER:

  "chroma" ChromaDB persistente en disco.
  "qdrant" Qdrant Cloud (HTTP, servicio gestionado).

La API pública es la misma para ambos, así que graph.py e ingestion.py no
cambian. Los imports de cada backend son perezosos: el proceso que usa Qdrant
no carga Chroma, y viceversa.

Metadatos: Chroma exige escalares; en Qdrant los None se convierten a -1 en
user_id y a cadena vacía en el resto, para que el filtrado sea equivalente.
"""
from threading import Lock

from app.config import get_settings

_chroma_client = None
_qdrant_client = None
_lock = Lock()


def _is_qdrant() -> bool:
    return get_settings().vector_provider == "qdrant"


def _get_chroma_collection():
    global _chroma_client
    with _lock:
        if _chroma_client is None:
            import chromadb

            _chroma_client = chromadb.PersistentClient(path=get_settings().vector_dir)
    return _chroma_client.get_or_create_collection(
        name=get_settings().collection_name,
        metadata={"hnsw:space": "cosine"},
    )


def _get_qdrant():
    global _qdrant_client
    settings = get_settings()
    with _lock:
        if _qdrant_client is None:
            from qdrant_client import QdrantClient

            if not settings.qdrant_url or not settings.qdrant_api_key:
                raise RuntimeError(
                    "VECTOR_PROVIDER=qdrant pero QDRANT_URL/QDRANT_API_KEY vacíos."
                )
            _qdrant_client = QdrantClient(
                url=settings.qdrant_url, api_key=settings.qdrant_api_key
            )
    _ensure_qdrant_collection(_qdrant_client, settings)
    return _qdrant_client


def _ensure_qdrant_collection(client, settings) -> None:
    from app.services.embeddings import embedding_dims
    from qdrant_client.models import Distance, VectorParams

    name = settings.qdrant_collection
    if not client.collection_exists(name):
        client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(
                size=embedding_dims(), distance=Distance.COSINE
            ),
        )


def _meta_scalars(meta: dict) -> dict:
    out = {}
    for k, v in meta.items():
        if v is None:
            out[k] = -1 if k == "user_id" else ""
        else:
            out[k] = v
    return out


def add_chunks(
    *,
    doc_id: int,
    texts: list[str],
    metadatas: list[dict],
    embeddings: list[list[float]],
) -> None:
    """Indexa los fragmentos de un documento. Los IDs son deterministas para
    poder reemplazar el documento sin duplicar fragmentos."""
    ids = [f"doc{doc_id}_chunk{i}" for i in range(len(texts))]

    if _is_qdrant():
        from qdrant_client.models import PointStruct

        client = _get_qdrant()
        settings = get_settings()
        points = [
            PointStruct(
                id=f"{doc_id}_{i}",
                vector=embeddings[i],
                payload={"text": texts[i], **_meta_scalars(metadatas[i])},
            )
            for i in range(len(texts))
        ]
        client.upsert(collection_name=settings.qdrant_collection, points=points)
        return

    collection = _get_chroma_collection()
    collection.upsert(
        ids=ids, documents=texts, metadatas=metadatas, embeddings=embeddings
    )


def fetch_documents(doc_type: str) -> list[dict]:
    """Todos los fragmentos de un tipo de documento (recuentos estructurados, E7)."""
    if _is_qdrant():
        client = _get_qdrant()
        settings = get_settings()
        qfilter = _build_qdrant_filter(doc_type=doc_type, user_id=None, visible_to=None)
        out: list[dict] = []
        offset = None
        while True:
            records, offset = client.scroll(
                collection_name=settings.qdrant_collection,
                scroll_filter=qfilter,
                limit=256,
                offset=offset,
                with_payload=True,
            )
            for pt in records:
                payload = pt.payload or {}
                out.append(
                    {
                        "text": payload.get("text", ""),
                        "metadata": {k: v for k, v in payload.items() if k != "text"},
                    }
                )
            if offset is None:
                break
        return out

    res = _get_chroma_collection().get(
        where={"doc_type": doc_type}, include=["documents", "metadatas"]
    )
    return [
        {"text": doc or "", "metadata": meta or {}}
        for doc, meta in zip(res.get("documents") or [], res.get("metadatas") or [])
    ]


def delete_document(doc_id: int) -> None:
    if _is_qdrant():
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        client = _get_qdrant()
        settings = get_settings()
        client.delete(
            collection_name=settings.qdrant_collection,
            points_selector=Filter(
                must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
            ),
        )
        return
    _get_chroma_collection().delete(where={"doc_id": doc_id})


def _build_qdrant_filter(
    *,
    doc_type: str | None,
    user_id: int | None,
    visible_to: int | None,
):
    from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue

    must = []
    if doc_type:
        must.append(FieldCondition(key="doc_type", match=MatchValue(value=doc_type)))
    if user_id is not None:
        must.append(FieldCondition(key="user_id", match=MatchValue(value=user_id)))
    if visible_to is not None:
        must.append(
            FieldCondition(key="user_id", match=MatchAny(any=[-1, visible_to]))
        )
    return Filter(must=must) if must else None


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

    title_contains y theme se filtran en Python tras la búsqueda, pidiendo más
    candidatos: Chroma 1.x no aplica $contains a cadenas multi-token y Qdrant
    no tiene equivalente directo.
    """
    if _is_qdrant():
        client = _get_qdrant()
        settings = get_settings()
        qfilter = _build_qdrant_filter(
            doc_type=doc_type, user_id=user_id, visible_to=visible_to
        )
        fetch_k = k * 5 if (theme or title_contains) else k
        try:
            res = client.query_points(
                collection_name=settings.qdrant_collection,
                query=query_embedding,
                query_filter=qfilter,
                limit=fetch_k,
                with_payload=True,
            )
        except Exception:
            return []
        out = []
        for pt in res.points:
            payload = pt.payload or {}
            meta = {kk: vv for kk, vv in payload.items() if kk != "text"}
            out.append(
                {
                    "text": payload.get("text", ""),
                    "score": float(pt.score),
                    "metadata": meta,
                }
            )
    else:
        collection = _get_chroma_collection()
        clauses = []
        if doc_type:
            clauses.append({"doc_type": doc_type})
        if title_contains:
            clauses.append({"title": {"$contains": title_contains}})
        if user_id is not None:
            clauses.append({"user_id": user_id})
        if visible_to is not None:
            clauses.append({"$or": [{"user_id": -1}, {"user_id": visible_to}]})
        if len(clauses) == 1:
            where = clauses[0]
        elif len(clauses) > 1:
            where = {"$and": clauses}
        else:
            where = None

        n_results = k * 5 if theme else k
        try:
            result = collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where,
                include=["documents", "metadatas", "distances"],
            )
        except Exception:
            return []

        out = []
        if not result or not result.get("documents"):
            return out
        for doc, meta, dist in zip(
            result["documents"][0], result["metadatas"][0], result["distances"][0]
        ):
            out.append({"text": doc, "score": 1.0 - float(dist), "metadata": meta})

    if title_contains:
        wanted = title_contains.strip().lower()
        out = [
            r for r in out if wanted in r["metadata"].get("title", "").lower()
        ] or out

    if theme:
        wanted_t = theme.strip().lower()
        with_theme = [
            r
            for r in out
            if wanted_t
            in [
                t.strip().lower()
                for t in r["metadata"].get("themes", "").split(",")
                if t.strip()
            ]
        ]
        out = with_theme or out

    return out[:k]


def count_chunks() -> int:
    if _is_qdrant():
        client = _get_qdrant()
        settings = get_settings()
        info = client.get_collection(settings.qdrant_collection)
        return int(info.points_count)
    return _get_chroma_collection().count()
