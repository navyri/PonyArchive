"""Importación de Pony API (https://ponyapi.net/).

Verificación real de 2026-10-17 (K01/K02):
  * 243 episodios, 555 personajes, 192 canciones disponibles.
  * Campos de episodio: id, name, url, season, episode, overall, airdate,
    storyby, writtenby, storyboard, song. NO incluyen sinopsis ni moraleja:
    las fichas narrativas se redactan aparte (DEC-10).
  * CORS: Access-Control-Allow-Origin: *. Límite por defecto: 50 registros.
  * Las rutas con "%20" devuelven 403: se usan IDs numéricos.
  * Licencia de los datos: CC BY-SA 3.0 (atribución obligatoria).
"""
from __future__ import annotations

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Document
from app.services.ingestion import index_document

LICENSE_NOTE = "CC BY-SA 3.0 — Pony API (datos de mlp.fandom.com)"
PAGE_SIZE = 100


def fetch_all(endpoint: str, params: dict | None = None) -> list[dict]:
    """Descarga paginada con limit/offset hasta agotar los registros."""
    base = get_settings().pony_api_url.rstrip("/")
    results: list[dict] = []
    offset = 0
    with httpx.Client(timeout=30.0) as client:
        while True:
            query = {"limit": PAGE_SIZE, "offset": offset, **(params or {})}
            response = client.get(f"{base}/{endpoint}", params=query)
            response.raise_for_status()
            payload = response.json()
            batch = payload.get("data", [])
            results.extend(batch)
            if len(batch) < PAGE_SIZE:
                return results
            offset += PAGE_SIZE


def _episode_text(ep: dict) -> str:
    season = ep.get("season", "?")
    number = ep.get("episode", "?")
    overall = ep.get("overall", "?")
    authors = "; ".join(
        filter(None, [ep.get("storyby", ""), ep.get("writtenby", "")])
    ) or "No documentado"
    storyboard = (ep.get("storyboard", "") or "").replace("\n", "; ") or "No documentado"
    return (
        f"EPISODIO de My Little Pony: Friendship Is Magic\n"
        f"Título: {ep.get('name', 'Sin título')}\n"
        f"Temporada {season}, episodio {number} (número global {overall}).\n"
        f"Fecha de emisión: {ep.get('airdate', 'desconocida')}.\n"
        f"Historia: {authors}.\n"
        f"Guion gráfico: {storyboard}.\n"
        f"Ficha de metadatos importada de Pony API. No contiene sinopsis: "
        f"para análisis narrativo consulta las fichas narrativas de la biblioteca.\n"
    )


def _character_text(ch: dict) -> str:
    kinds = "; ".join(ch.get("kind", [])) or "No documentado"
    residence = (ch.get("residence", "") or "").replace("\n", "; ") or "No documentado"
    occupation = (ch.get("occupation", "") or "").replace("\n", "; ") or "No documentado"
    alias = ch.get("alias")
    return (
        f"PERSONAJE de My Little Pony: Friendship Is Magic\n"
        f"Nombre: {ch.get('name', 'Sin nombre')}\n"
        f"Alias: {alias if alias else 'No tiene documentado'}\n"
        f"Tipo: {kinds}.\n"
        f"Sexo: {ch.get('sex', 'No documentado')}.\n"
        f"Residencia: {residence}.\n"
        f"Ocupación: {occupation}.\n"
        f"Ficha de metadatos importada de Pony API.\n"
    )


def import_episodes(db: Session) -> dict:
    episodes = fetch_all("episode/all", {"image": "none", "song": "none"})
    created = skipped = 0
    for ep in episodes:
        text = _episode_text(ep)
        before = db.query(Document).count()
        index_document(
            db,
            title=str(ep.get("name", "Sin título")),
            text=text,
            doc_type="episodio",
            source="ponyapi",
            source_id=str(ep.get("id")),
            source_url=ep.get("url", ""),
            license_note=LICENSE_NOTE,
        )
        if db.query(Document).count() > before:
            created += 1
        else:
            skipped += 1
    return {"descargados": len(episodes), "indexados": created, "omitidos_duplicados": skipped}


def import_characters(db: Session) -> dict:
    characters = fetch_all("character/all", {"image": "none", "kind": "name"})
    created = skipped = 0
    for ch in characters:
        text = _character_text(ch)
        before = db.query(Document).count()
        index_document(
            db,
            title=str(ch.get("name", "Sin nombre")),
            text=text,
            doc_type="personaje",
            source="ponyapi",
            source_id=str(ch.get("id")),
            source_url=ch.get("url", ""),
            license_note=LICENSE_NOTE,
        )
        if db.query(Document).count() > before:
            created += 1
        else:
            skipped += 1
    return {"descargados": len(characters), "indexados": created, "omitidos_duplicados": skipped}
