"""Consulta del catálogo importado (personajes y episodios).

Estas rutas usan consultas SQL directas sobre el catálogo, no similitud de
embeddings: son idóneas para listar y contar (estrategia E7 del grafo).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Document, User
from app.security import get_current_user

router = APIRouter(prefix="/library", tags=["biblioteca"])


def _search_docs(db: Session, doc_type: str, q: str | None, limit: int) -> list[Document]:
    query = db.query(Document).filter(Document.doc_type == doc_type, Document.status == "indexado")
    if q:
        query = query.filter(Document.title.ilike(f"%{q}%"))
    return query.order_by(Document.title).limit(limit).all()


@router.get("/characters")
def list_characters(
    q: str | None = None,
    limit: int = 50,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    docs = _search_docs(db, "personaje", q, min(limit, 200))
    return [
        {"id": d.id, "name": d.title, "source_id": d.source_id, "source_url": d.source_url}
        for d in docs
    ]


@router.get("/episodes")
def list_episodes(
    q: str | None = None,
    limit: int = 50,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    docs = _search_docs(db, "episodio", q, min(limit, 300))
    return [
        {"id": d.id, "name": d.title, "source_id": d.source_id, "source_url": d.source_url}
        for d in docs
    ]


@router.get("/documents/{document_id}")
def get_document(
    document_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Documento no encontrado.")
    return {
        "id": doc.id,
        "title": doc.title,
        "doc_type": doc.doc_type,
        "source": doc.source,
        "source_id": doc.source_id,
        "source_url": doc.source_url,
        "chunk_count": doc.chunk_count,
        "license_note": doc.license_note,
    }
