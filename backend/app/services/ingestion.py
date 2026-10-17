"""Pipeline de carga y procesamiento de documentos (§2.4 del PDF):

1. Recibir el archivo  2. Extraer el contenido  3. Dividir en fragmentos
4. Generar embeddings  5. Almacenar en la base vectorial  6. Confirmar al usuario
"""
from __future__ import annotations

import hashlib
from io import BytesIO

from docx import Document as DocxDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Document
from app.services.embeddings import embed_passages
from app.services.themes import detect_themes
from app.services.vectorstore import add_chunks, delete_document

SUPPORTED_EXTENSIONS = (".txt", ".md", ".csv", ".pdf", ".docx")


class ExtractionError(ValueError):
    """El archivo no se puede procesar (formato no soportado o ilegible)."""


def extract_text(filename: str, data: bytes) -> str:
    """Extrae texto plano según el formato. Los formatos multimedia (JPG/MP4/MP3)
    del enunciado son *sugeridos*, no obligatorios: quedan documentados como fuera
    de alcance del MVP."""
    lower = filename.lower()
    if lower.endswith((".txt", ".md")):
        return data.decode("utf-8", errors="replace")
    if lower.endswith(".csv"):
        return data.decode("utf-8", errors="replace")
    if lower.endswith(".pdf"):
        reader = PdfReader(BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    if lower.endswith(".docx"):
        doc = DocxDocument(BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs)
    raise ExtractionError(
        f"Formato no soportado: {filename}. Usa PDF, TXT, Markdown o CSV."
    )


def chunk_text(text: str) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=get_settings().chunk_size,
        chunk_overlap=get_settings().chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return [c.strip() for c in splitter.split_text(text) if c.strip()]


def index_document(
    db: Session,
    *,
    title: str,
    text: str,
    doc_type: str,
    source: str,
    user_id: int | None = None,
    source_id: str = "",
    source_url: str = "",
    license_note: str = "",
) -> Document:
    """Indexa un texto completo: crea la fila del documento, lo fragmenta,
    genera sus embeddings y los guarda en la base vectorial.

    Evita duplicados por huella del contenido (K05): si el mismo texto ya está
    indexado, se devuelve el documento existente sin reindexar.
    """
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    # Deduplicación: global para la biblioteca compartida (user_id NULL) y por
    # usuario para las cargas, de modo que dos usuarios con el mismo archivo
    # tengan cada uno su copia visible solo para él (aislamiento, T10).
    query = db.query(Document).filter(Document.content_hash == content_hash)
    query = query.filter(Document.user_id.is_(None) if user_id is None else Document.user_id == user_id)
    existing = query.first()
    if existing:
        return existing

    doc = Document(
        user_id=user_id,
        title=title,
        doc_type=doc_type,
        source=source,
        source_id=source_id,
        source_url=source_url,
        license_note=license_note,
        content_hash=content_hash,   # imprescindible para evitar duplicados (K05)
        status="procesando",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    try:
        chunks = chunk_text(text)
        if not chunks:
            raise ExtractionError("El documento no contiene texto extraíble.")
        embeddings = embed_passages(chunks)
        themes = detect_themes(text)
        # Clave filtrable: Chroma 1.x hace coincidencia de $contains por tokens,
        # por lo que "trabajo en equipo" no coincide como cadena; se usa una clave
        # sin espacios (trabajo_en_equipo) y se conserva la forma legible.
        theme_keys = "|".join(t.replace(" ", "_") for t in themes)
        metadatas = [
            {
                "doc_id": doc.id,
                "doc_type": doc_type,
                "source": source,
                "title": title,
                "source_url": source_url,
                "continuity": "fim",
                "themes": ",".join(themes),
                "theme_keys": theme_keys,
                "chunk_index": i,
                "user_id": user_id if user_id is not None else -1,
            }
            for i in range(len(chunks))
        ]
        add_chunks(doc_id=doc.id, texts=chunks, metadatas=metadatas, embeddings=embeddings)
        doc.chunk_count = len(chunks)
        doc.status = "indexado"
    except Exception as exc:  # cualquier fallo deja estado coherente y visible
        doc.status = "error"
        db.commit()
        raise ExtractionError(f"No se pudo indexar '{title}': {exc}") from exc

    db.commit()
    db.refresh(doc)
    return doc


def remove_document(db: Session, doc: Document) -> None:
    delete_document(doc.id)
    db.delete(doc)
    db.commit()
