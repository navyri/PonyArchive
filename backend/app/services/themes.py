"""Taxonomía temática: etiquetas del índice para recuperación y clasificación.

Las etiquetas se asignan a los documentos/fragmentos. La asignación automática
se hace por coincidencia de palabras clave sobre el texto del documento; es una
regla determinista documentada, no una "opinión" del modelo. El texto del
documento sigue siendo la única fuente de hechos.
"""
from __future__ import annotations

THEMES: dict[str, list[str]] = {
    "confianza": ["confía", "confianza", "confiar", "creer en", "fiar", "desconfianza"],
    "celos": ["celos", "celosa", "celoso", "envidia", "envidiosa", "competencia"],
    "reconciliación": ["reconciliación", "reconciliar", "perdón", "perdonar", "disculparse", "enemistad"],
    "trabajo en equipo": ["equipo", "juntas", "colaborar", "cooperar", "ayudarse", "cooperación"],
    "amistad": ["amistad", "amiga", "amigo", "mejor amiga", "compañeras"],
    "honestidad": ["honestidad", "honesta", "verdad", "mentira", "mentir", "sinceridad"],
    "responsabilidad": ["responsabilidad", "responsable", "deber", "compromiso", "encargo"],
    "liderazgo": ["líder", "liderazgo", "liderar", "dirigir", "princesa"],
    "valentía": ["valentía", "valiente", "miedo", "atreverse", "coraje"],
    "generosidad": ["generosidad", "generosa", "compartir", "regalar", "dar a otros"],
    "paciencia": ["paciencia", "paciente", "esperar", "prisa", "impaciencia"],
}


def detect_themes(text: str) -> list[str]:
    """Devuelve las etiquetas cuyas palabras clave aparecen en el texto."""
    lowered = text.lower()
    found = [theme for theme, keywords in THEMES.items() if any(k in lowered for k in keywords)]
    return found or ["amistad"]


def theme_from_query(text: str) -> str | None:
    """Detecta el tema dominante de una pregunta del usuario."""
    lowered = text.lower()
    best_theme, best_hits = None, 0
    for theme, keywords in THEMES.items():
        hits = sum(1 for k in keywords if k in lowered)
        if hits > best_hits:
            best_theme, best_hits = theme, hits
    return best_theme
