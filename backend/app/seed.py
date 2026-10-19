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
from app.services.vectorstore import catalogo_compartido, purgar_usuarios_huerfanos

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


def _hidratar_catalogo(db: Session) -> int:
    """Reconstruye las filas del catálogo compartido desde el índice vectorial.

    En un despliegue nuevo la base relacional arranca vacía pero el índice de
    la nube ya contiene la biblioteca: se recuperan sus metadatos sin re-embeber.
    """
    creados = 0
    purgar_usuarios_huerfanos()
    for fila in catalogo_compartido():
        if db.get(Document, fila["doc_id"]) is not None:
            continue
        db.add(
            Document(
                id=fila["doc_id"],
                user_id=None,
                title=fila.get("title", "") or "(sin título)",
                doc_type=fila.get("doc_type", "documento"),
                source=fila.get("source", ""),
                source_id=fila.get("source_id", "") or f"idx-{fila['doc_id']}",
                source_url=fila.get("source_url", ""),
                status="indexado",
                chunk_count=fila.get("chunk_count", 0),
                license_note=(
                    "Metadatos reconstruidos desde el índice vectorial; datos de "
                    "Pony API y Fandom bajo CC BY-SA 3.0."
                ),
            )
        )
        creados += 1
    db.commit()
    return creados


def seed_if_empty(db: Session) -> dict:
    """Indexa las fichas o reconstruye el catálogo si la biblioteca está vacía."""
    if db.query(Document).filter(Document.status != "error").count() > 0:
        return {"estado": "ya_indexada", "documentos": db.query(Document).count()}

    # Una siembra interrumpida deja filas en error que bloquearían el reintento.
    db.query(Document).filter(Document.status == "error").delete(
        synchronize_session=False
    )
    db.commit()

    hidratados = _hidratar_catalogo(db)
    if hidratados:
        return {
            "estado": "catalogo_hidratado",
            "documentos": db.query(Document).count(),
            "filas": hidratados,
        }

    files = sorted(SEED_DIR.glob("*.json"))
    created = 0
    for path in files:
        if path.name == "contexto_curso.json":
            continue  # se trata aparte: ver seed_contexto()
        items = json.loads(path.read_text(encoding="utf-8"))
        for item in items:
            # Un fallo puntual (p. ej. red en el arranque) no aborta la siembra.
            try:
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
            except Exception as exc:
                print(f"[PonyArchive] ficha {item.get('codigo')} omitida: {exc}")
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
        try:
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
        except Exception as exc:
            print(f"[PonyArchive] nota {item.get('titulo')} omitida: {exc}")
    return {"estado": "notas_indexadas", "creadas": creadas}
