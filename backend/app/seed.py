"""Semilla inicial: fichas narrativas de la biblioteca.

La Pony API no contiene sinopsis ni moralejas, así que estas fichas se redactan
para el proyecto y se indexan como documentos (doc_type = "ficha_narrativa",
source = "semilla"). El JSON es la fuente de verdad de la aplicación."""
from __future__ import annotations

import json
import os
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Document
from app.services.ingestion import index_document

# En contenedor, PONYARCHIVE_SEED_DIR apunta a /app/seed (fuera del volumen de datos:
# docker-compose monta /app/data y enmascararía cualquier semilla ahí dentro).
SEED_DIR = Path(
    os.environ.get("PONYARCHIVE_SEED_DIR")
    or Path(__file__).resolve().parents[1] / "data" / "seed"
)
LICENSE = "Ficha narrativa original de PonyArchive (redacción propia)"


def _format_ficha(item: dict) -> str:
    return (
        f"FICHA NARRATIVA — My Little Pony: Friendship Is Magic\n"
        f"Episodio: {item['titulo']}\n"
        f"Temporada y episodio: {item['codigo']}\n"
        f"Temas documentados: {', '.join(item['temas'])}.\n"
        f"\nSINOPSIS DOCUMENTADA:\n{item['sinopsis']}\n"
        f"\nCONFLICTO:\n{item['conflicto']}\n"
        f"\nRESOLUCIÓN:\n{item['resolucion']}\n"
        f"\nLECCIÓN DOCUMENTADA:\n{item['leccion']}\n"
    )


def seed_if_empty(db: Session) -> dict:
    """Indexa las fichas solo si la biblioteca está vacía (idempotente por hash)."""
    if db.query(Document).count() > 0:
        return {"estado": "ya_indexada", "documentos": db.query(Document).count()}

    files = sorted(SEED_DIR.glob("*.json"))
    created = 0
    for path in files:
        if path.name == "contexto_curso.json":
            continue  # se trata aparte: ver seed_contexto()
        items = json.loads(path.read_text(encoding="utf-8"))
        for item in items:
            index_document(
                db,
                title=item["titulo"],
                text=_format_ficha(item),
                doc_type="ficha_narrativa",
                source="semilla",
                source_id=item["codigo"],
                license_note=LICENSE,
            )
            created += 1
    return {"estado": "semilla_aplicada", "documentos": db.query(Document).count(), "fichas": created}


def seed_contexto(db: Session) -> dict:
    """Notas de contexto del curso. Idempotente por título."""
    path = SEED_DIR / "contexto_curso.json"
    if not path.exists():
        return {"estado": "sin_notas", "creadas": 0}

    creadas = 0
    for item in json.loads(path.read_text(encoding="utf-8")):
        ya_existe = db.query(Document).filter(Document.title == item["titulo"]).first()
        if ya_existe:
            continue
        index_document(
            db,
            title=item["titulo"],
            text=item["texto"],
            doc_type="nota_curso",
            source="semilla",
            source_id=item.get("codigo"),
            license_note=LICENSE,
        )
        creadas += 1
    return {"estado": "notas_indexadas", "creadas": creadas}
