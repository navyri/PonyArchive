"""Endpoints de carga, listado y borrado de documentos (§2.4 del PDF)."""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Document, User
from app.security import get_current_user
from app.services.ingestion import (
    SUPPORTED_EXTENSIONS,
    ExtractionError,
    index_document,
    remove_document,
)

router = APIRouter(prefix="/documents", tags=["documentos"])
settings = get_settings()


def _doc_payload(doc: Document) -> dict:
    return {
        "id": doc.id,
        "title": doc.title,
        "doc_type": doc.doc_type,
        "source": doc.source,
        "source_id": doc.source_id,
        "source_url": doc.source_url,
        "status": doc.status,
        "chunk_count": doc.chunk_count,
        "license_note": doc.license_note,
        "owner": "personal" if doc.user_id else "biblioteca",
        "created_at": doc.created_at.isoformat(),
    }


@router.post("", status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Recibe un archivo del frontend y lo procesa: extracción → fragmentación →
    embeddings → base vectorial. Devuelve confirmación con el número de fragmentos."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="El archivo no tiene nombre.")
    if not file.filename.lower().endswith(SUPPORTED_EXTENSIONS):
        raise HTTPException(
            status_code=415,
            detail=f"Formato no soportado. Usa: {', '.join(SUPPORTED_EXTENSIONS)}",
        )

    data = await file.read()
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"El archivo supera {settings.max_upload_mb} MB.")

    try:
        text = extract_or_fail(file.filename, data)
        doc = index_document(
            db,
            title=file.filename,
            text=text,
            doc_type="upload",
            source="upload",
            user_id=user.id,
            license_note="Documento aportado por el usuario",
        )
    except ExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return {
        "message": f"Documento '{doc.title}' procesado e indexado.",
        "document": _doc_payload(doc),
        "already_indexed": doc.chunk_count == 0,
    }


def extract_or_fail(filename: str, data: bytes) -> str:
    from app.services.ingestion import extract_text

    text = extract_text(filename, data)
    if not text.strip():
        raise ExtractionError("El documento no contiene texto extraíble.")
    return text


@router.get("")
def list_documents(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    doc_type: str | None = None,
    scope: str = "all",
):
    """Lista los documentos: los compartidos de la biblioteca y los propios del usuario.

    Nunca muestra documentos privados de otros usuarios (aislamiento, T10):
    scope=all = biblioteca compartida + los míos.
    """
    query = db.query(Document)
    if doc_type:
        query = query.filter(Document.doc_type == doc_type)
    if scope == "mine":
        query = query.filter(Document.user_id == user.id)
    elif scope == "shared":
        query = query.filter(Document.user_id.is_(None))
    else:
        query = query.filter(
            or_(Document.user_id == user.id, Document.user_id.is_(None))
        )
    docs = query.order_by(Document.created_at.desc()).limit(300).all()
    return [_doc_payload(d) for d in docs]


@router.delete("/{document_id}", status_code=204)
def delete_document_endpoint(
    document_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Solo el propietario puede borrar sus documentos. Los documentos de la
    biblioteca compartida no se borran desde el cliente (K12)."""
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Documento no encontrado.")
    if doc.user_id != user.id:
        raise HTTPException(status_code=403, detail="Solo puedes borrar tus propios documentos.")
    remove_document(db, doc)
    return None
