"""Estado compartido del grafo de LangGraph.

El estado es el único canal de comunicación entre nodos: cada nodo recibe el
estado completo y devuelve únicamente los campos que modifica.
"""
from typing import TypedDict


class Source(TypedDict):
    doc_id: int
    title: str
    doc_type: str
    source: str
    source_url: str
    fragment: str
    score: float


class AgentState(TypedDict, total=False):
    # Entrada
    question: str
    user_id: int
    conversation_id: int
    history: list[list[str]]          # [["usuario", "..."], ["asistente", "..."]]

    # Nodo 1 — validación de intención y filtros
    intent: str                       # factual | tematica | comparacion | catalogo | fuera_de_dominio | ambigua
    theme: str | None                 # etiqueta temática de Friendship Journal
    title_filter: str | None          # continuidad/episodio/personaje citado en la pregunta
    doc_type_filter: str | None       # episodio | personaje | cancion | ficha_narrativa | upload
    compare_items: list[str]          # elementos a comparar (intent = comparacion)
    clarification: str | None         # pregunta de aclaración si la consulta es ambigua

    # Nodo 2 — recuperación
    retrieved: list[Source]
    retrieval_notes: list[str]        # fragmentos descartados por el umbral (auditoría)

    # Nodo 3 — suficiencia
    sufficient: bool
    refusal_reason: str | None

    # Nodos de respuesta
    answer: str
    sources: list[Source]
    refused: bool
    grounded: bool
    retry_count: int
