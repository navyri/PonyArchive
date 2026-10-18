"""Sinopsis de episodios desde la wiki de Fandom (mlp.fandom.com).

Pony API no incluye sinopsis; la wiki canónica que enlaza sí las tiene de todos
los episodios. Se consulta la API de MediaWiki (action=parse → wikitext) y se
extrae la sección ==Summary==, limpia a texto plano. Licencia del contenido:
CC BY-SA 3.0 (atribución obligatoria). Fallos de red se toleran: el episodio
queda con sus metadatos y sin sinopsis en vez de abortar la importación.
"""
from __future__ import annotations

import re
import time
from urllib.parse import unquote, urlparse

import httpx

FANDOM_API = "https://mlp.fandom.com/api.php"
USER_AGENT = "PonyArchive/1.0 (proyecto academico; uso educativo)"
REQUEST_PAUSE_S = 0.15  # cortesía: evita golpear la wiki con 243 peticiones seguidas

# caché en memoria: misma sesión de importación no repite peticiones
_synopsis_cache: dict[str, str | None] = {}


def page_title_from_url(url: str) -> str:
    """Extrae el título de página de una URL de Fandom (…/wiki/Título_aquí)."""
    if not url:
        return ""
    path = urlparse(url).path
    if "/wiki/" not in path:
        return ""
    return unquote(path.split("/wiki/", 1)[1]).replace("_", " ").strip()


def _clean_wikitext(text: str) -> str:
    """Convierte wikitext de Fandom a texto plano legible para el RAG."""
    # referencias al pie
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.S)
    text = re.sub(r"<ref[^>]*/>", "", text)
    # archivos e imágenes completos (antes de tocar los enlaces)
    text = re.sub(r"\[\[(?:File|Image|Media):[^\]]*\]\]", "", text, flags=re.I)
    # plantillas anidadas: quitar por capas
    for _ in range(3):
        text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    # enlaces internos: [[a|b]] -> b ; [[a]] -> a
    text = re.sub(r"\[\[([^|\]]+\|)+([^\]]+)\]\]", r"\2", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    # etiquetas html sobrantes
    text = re.sub(r"<[^>]+>", "", text)
    # énfasis ('''negrita''', ''cursiva'')
    text = re.sub(r"'{2,}", "", text)
    # encabezados ===título=== -> título
    text = re.sub(r"={2,}\s*([^=]+?)\s*={2,}", r"\1", text)
    # artefactos de miniatura que queden sueltos
    text = re.sub(r"\bthumb\|(?:left\|)?", "", text)
    # espacios y saltos
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _fetch_summary(title: str) -> str | None:
    """Descarga el wikitext de una página y devuelve la sección Summary limpia."""
    if not title:
        return None
    params = {"action": "parse", "page": title, "prop": "wikitext", "format": "json"}
    with httpx.Client(timeout=25.0, headers={"User-Agent": USER_AGENT}) as client:
        for attempt in range(2):
            try:
                response = client.get(FANDOM_API, params=params)
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                payload = response.json()
                wikitext = payload["parse"]["wikitext"]["*"]
                break
            except (httpx.HTTPError, KeyError, ValueError):
                if attempt == 0:
                    time.sleep(0.5)
                    continue
                return None
    match = re.search(
        r"==\s*Summary\s*==(.*?)(?=\n==[^=]|\Z)", wikitext, flags=re.S | re.I
    )
    if not match:
        return None
    clean = _clean_wikitext(match.group(1))
    return clean or None


def fetch_synopsis(title: str) -> str | None:
    """Devuelve la sinopsis en texto plano de un episodio (o None si no hay).

    Usa caché en memoria para no repetir la petición del mismo título.
    """
    if title in _synopsis_cache:
        return _synopsis_cache[title]
    time.sleep(REQUEST_PAUSE_S)
    synopsis = _fetch_summary(title)
    _synopsis_cache[title] = synopsis
    return synopsis
