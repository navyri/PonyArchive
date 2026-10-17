"""Semilla inicial: fichas narrativas propias de Friendship Journal.

DEC-10: la Pony API no contiene sinopsis ni moralejas, así que estas fichas se
redactan para el proyecto y se indexan como documentos de la biblioteca
(doc_type = "ficha_narrativa", source = "semilla").

El contenido describe lo que ocurre en cada episodio; no inventa datos fuera de
lo documentado en la serie. Si detectas un error factual, corrige el JSON: es la
fuente de verdad de la aplicación.
"""
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Document
from app.services.ingestion import index_document

SEED_DIR = Path(__file__).resolve().parents[1] / "data" / "seed"
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
