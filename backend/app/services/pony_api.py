"""Importación de Pony API (https://ponyapi.net/).

Datos verificados: 243 episodios, 555 personajes y 192 canciones. Los episodios
no incluyen sinopsis ni las canciones su letra (derechos de autor); la prosa de
personajes y las sinopsis se enriquecen con la wiki de Fandom. Fichas narrativas
propias aparte. Licencia de los datos: CC BY-SA 3.0 (atribución obligatoria).
Las rutas con "%20" devuelven 403: se usan IDs numéricos."""
from __future__ import annotations

import hashlib

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Document
from app.services.fandom import fetch_lead, fetch_synopsis, page_title_from_url
from app.services.ingestion import index_document, remove_document

LICENSE_NOTE = (
    "CC BY-SA 3.0 — Pony API (metadatos) y wiki de Fandom mlp.fandom.com "
    "(sinopsis y descripciones)"
)
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


def _episode_text(ep: dict, synopsis: str | None = None) -> str:
    season = ep.get("season", "?")
    number = ep.get("episode", "?")
    overall = ep.get("overall", "?")
    authors = "; ".join(
        filter(None, [ep.get("storyby", ""), ep.get("writtenby", "")])
    ) or "No documentado"
    storyboard = (ep.get("storyboard", "") or "").replace("\n", "; ") or "No documentado"
    lines = [
        f"EPISODIO de My Little Pony: Friendship Is Magic\n"
        f"Título: {ep.get('name', 'Sin título')}\n"
        f"Temporada {season}, episodio {number} (número global {overall}).\n"
        f"Fecha de emisión: {ep.get('airdate', 'desconocida')}.\n"
        f"Historia: {authors}.\n"
        f"Guion gráfico: {storyboard}.\n"
    ]
    if synopsis:
        lines.append(f"SINOPSIS (wiki de Fandom):\n{synopsis}\n")
    else:
        lines.append(
            f"Ficha de metadatos importada de Pony API. No contiene sinopsis: "
            f"para análisis narrativo consulta las fichas narrativas de la biblioteca.\n"
        )
    return "".join(lines)


def _character_text(ch: dict, lead: str | None = None) -> str:
    kinds = "; ".join(ch.get("kind", [])) or "No documentado"
    residence = (ch.get("residence", "") or "").replace("\n", "; ") or "No documentado"
    occupation = (ch.get("occupation", "") or "").replace("\n", "; ") or "No documentado"
    alias = ch.get("alias")
    text = (
        f"PERSONAJE de My Little Pony: Friendship Is Magic\n"
        f"Nombre: {ch.get('name', 'Sin nombre')}\n"
        f"Alias: {alias if alias else 'No tiene documentado'}\n"
        f"Tipo: {kinds}.\n"
        f"Sexo: {ch.get('sex', 'No documentado')}.\n"
        f"Residencia: {residence}.\n"
        f"Ocupación: {occupation}.\n"
        f"Ficha de metadatos importada de Pony API.\n"
    )
    if lead:
        # La prosa de la wiki distingue al personaje: sin ella, "¿Quién es X?"
        # solo dispone de metadatos y el modelo rehúsa con razón.
        text += f"\nDESCRIPCIÓN (wiki de Fandom, CC BY-SA 3.0):\n{lead}\n"
    return text


def _song_text(song: dict) -> str:
    return (
        f"CANCION de My Little Pony: Friendship Is Magic\n"
        f"Título: {song.get('name', 'Sin título')}\n"
        f"Episodio: {song.get('episode') or 'No documentado'}.\n"
        f"Música: {song.get('musicby') or 'No documentado'}.\n"
        f"Autoría de la letra: {song.get('lyricsby') or 'No documentado'}.\n"
        f"Duración: {song.get('length') or 'No documentada'}.\n"
        f"Tonalidad: {song.get('keysignature') or 'No documentada'}.\n"
        f"Ficha de metadatos importada de Pony API. No incluye la letra "
        f"(derechos de autor): la fuente enlazada es la página de Fandom.\n"
    )


def import_episodes(db: Session) -> dict:
    """Importa los episodios de Pony API y les añade la sinopsis de Fandom.

    Idempotente por source_id: los episodios ya indexados con sinopsis se omiten;
    los que existan sin ella (formato antiguo) se reemplazan. Seguro de ejecutar
    en cada arranque sin duplicar ni re-descargar todo.
    """
    episodes = fetch_all("episode/all", {"image": "none", "song": "none"})
    created = updated = skipped = con_sinopsis = 0
    for ep in episodes:
        title = str(ep.get("name", "Sin título"))
        source_id = str(ep.get("id"))
        synopsis = fetch_synopsis(page_title_from_url(ep.get("url", "")))
        if synopsis:
            con_sinopsis += 1
        text = _episode_text(ep, synopsis)
        outcome = _upsert_library_doc(
            db,
            title=title,
            text=text,
            doc_type="episodio",
            source_id=source_id,
            source_url=ep.get("url", ""),
        )
        if outcome == "created":
            created += 1
        elif outcome == "updated":
            updated += 1
        else:
            skipped += 1
    return {
        "descargados": len(episodes),
        "indexados": created,
        "actualizados": updated,
        "omitidos_duplicados": skipped,
        "con_sinopsis": con_sinopsis,
    }


def _upsert_library_doc(
    db: Session,
    *,
    title: str,
    text: str,
    doc_type: str,
    source_id: str,
    source_url: str,
) -> str:
    """Indexa un documento de biblioteca identificado por (doc_type, source_id).

    Devuelve "created", "updated" u "skipped". Si ya existe con el mismo texto se
    omite; si existe con texto distinto (p. ej. se añadió la sinopsis) se
    reemplaza para evitar duplicados. Nunca toca documentos de usuarios.
    """
    existing = (
        db.query(Document)
        .filter(
            Document.doc_type == doc_type,
            Document.source_id == source_id,
            Document.user_id.is_(None),
        )
        .first()
    )
    new_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if existing and existing.content_hash == new_hash:
        return "skipped"
    if existing:
        remove_document(db, existing)
    index_document(
        db,
        title=title,
        text=text,
        doc_type=doc_type,
        source="ponyapi",
        source_id=source_id,
        source_url=source_url,
        license_note=LICENSE_NOTE,
    )
    return "updated" if existing else "created"


def import_characters(db: Session) -> dict:
    """Importa los personajes de Pony API y les añade la entradilla de Fandom.

    Idempotente por source_id (igual que los episodios): los que ya tienen la
    descripción se omiten; los metadatos viejos se reemplazan una sola vez.
    """
    characters = fetch_all("character/all", {"image": "none", "kind": "name"})
    created = updated = skipped = con_descripcion = 0
    for ch in characters:
        lead = fetch_lead(page_title_from_url(ch.get("url", "")))
        if lead:
            con_descripcion += 1
        outcome = _upsert_library_doc(
            db,
            title=str(ch.get("name", "Sin nombre")),
            text=_character_text(ch, lead),
            doc_type="personaje",
            source_id=str(ch.get("id")),
            source_url=ch.get("url", ""),
        )
        if outcome == "created":
            created += 1
        elif outcome == "updated":
            updated += 1
        else:
            skipped += 1
    return {
        "descargados": len(characters),
        "indexados": created,
        "actualizados": updated,
        "omitidos_duplicados": skipped,
        "con_descripcion": con_descripcion,
    }


def import_songs(db: Session) -> dict:
    """Importa las canciones de Pony API (metadatos verificados, sin letras)."""
    songs = fetch_all("song/all")
    created = updated = skipped = 0
    for song in songs:
        outcome = _upsert_library_doc(
            db,
            title=str(song.get("name", "Sin título")),
            text=_song_text(song),
            doc_type="cancion",
            source_id=str(song.get("id")),
            source_url=song.get("url", ""),
        )
        if outcome == "created":
            created += 1
        elif outcome == "updated":
            updated += 1
        else:
            skipped += 1
    return {
        "descargadas": len(songs),
        "indexadas": created,
        "actualizadas": updated,
        "omitidas": skipped,
    }
