"""Friendship Journal: búsqueda y análisis temático de historias documentadas.

Funciona sobre los mismos documentos del grafo de LangGraph: no es un agente
separado (decisión de alcance del proyecto) sino una forma de consultar la
biblioteca con filtros temáticos y de comparación.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.agents.graph import get_graph
from app.models import User
from app.security import get_current_user
from app.services.themes import all_theme_names

router = APIRouter(prefix="/journal", tags=["friendship journal"])


class ThemeQuery(BaseModel):
    theme: str = Field(min_length=2, max_length=60)
    question: str | None = Field(default=None, max_length=1000)


class CompareQuery(BaseModel):
    item_a: str = Field(min_length=2, max_length=120)
    item_b: str = Field(min_length=2, max_length=120)


@router.get("/themes")
def themes(user: User = Depends(get_current_user)):
    return {"themes": all_theme_names()}


@router.post("/query")
def thematic_query(payload: ThemeQuery, user: User = Depends(get_current_user)):
    """Consulta temática: la pregunta se formula con el tema explícito para que
    el grafo recupere con ese filtro."""
    if payload.theme.lower() not in all_theme_names():
        raise HTTPException(status_code=400, detail=f"Tema no reconocido. Usa: {all_theme_names()}")
    question = payload.question or f"¿Qué episodios y personajes documentan el tema {payload.theme}?"
    result = get_graph().invoke(
        {"question": question, "user_id": user.id, "conversation_id": 0, "history": []}
    )
    return {
        "theme": payload.theme,
        "answer": result.get("answer", ""),
        "sources": result.get("sources", []),
        "refused": bool(result.get("refused")),
    }


@router.post("/compare")
def compare(payload: CompareQuery, user: User = Depends(get_current_user)):
    """Comparación documentada entre dos elementos de la biblioteca."""
    question = (
        f"Compara {payload.item_a} y {payload.item_b} según la documentación disponible: "
        f"¿qué tienen en común y en qué se diferencian?"
    )
    result = get_graph().invoke(
        {
            "question": question,
            "user_id": user.id,
            "conversation_id": 0,
            "history": [],
            "intent": "comparacion",
            "compare_items": [payload.item_a, payload.item_b],
        }
    )
    return {
        "answer": result.get("answer", ""),
        "sources": result.get("sources", []),
        "refused": bool(result.get("refused")),
        "refusal_reason": result.get("refusal_reason"),
    }
