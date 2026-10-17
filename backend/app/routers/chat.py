"""Endpoints de negocio: chat con el agente e historial por usuario.

Todas las rutas de este módulo exigen Bearer token (estrategia: ningún endpoint
de negocio sin autenticación) y solo devuelven datos del usuario autenticado.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agents.graph import get_graph
from app.database import get_db
from app.models import Conversation, Message, User
from app.security import get_current_user

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    conversation_id: int | None = None


@router.post("")
def ask(payload: ChatRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Envía una pregunta al agente LangGraph y devuelve respuesta, fuentes y conversación."""
    if payload.conversation_id is not None:
        conversation = db.get(Conversation, payload.conversation_id)
        if conversation is None or conversation.user_id != user.id:
            raise HTTPException(status_code=403, detail="La conversación no pertenece a este usuario.")

    history = []
    if payload.conversation_id:
        previous = (
            db.query(Message)
            .filter(Message.conversation_id == payload.conversation_id)
            .order_by(Message.created_at.desc())
            .limit(6)
            .all()
        )
        history = [[m.role, m.content] for m in reversed(previous)]

    state = {
        "question": payload.question.strip(),
        "user_id": user.id,
        "conversation_id": payload.conversation_id or 0,
        "history": history,
    }
    result = get_graph().invoke(state)

    return {
        "answer": result.get("answer", ""),
        "sources": result.get("sources", []),
        "refused": bool(result.get("refused")),
        "intent": result.get("intent"),
        "theme": result.get("theme"),
        "sufficient": bool(result.get("sufficient", False)),
        "retrieval_notes": result.get("retrieval_notes", []),
        "refusal_reason": result.get("refusal_reason"),
        "conversation_id": result.get("conversation_id"),
    }


@router.get("/conversations")
def list_conversations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(Conversation)
        .filter(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )
    return [
        {"id": c.id, "title": c.title, "updated_at": c.updated_at.isoformat()}
        for c in rows
    ]


@router.get("/conversations/{conversation_id}")
def get_conversation(
    conversation_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation = db.get(Conversation, conversation_id)
    if conversation is None or conversation.user_id != user.id:
        raise HTTPException(status_code=404, detail="Conversación no encontrada.")
    import json

    return {
        "id": conversation.id,
        "title": conversation.title,
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "sources": json.loads(m.sources_json or "[]"),
                "refused": m.refused,
                "created_at": m.created_at.isoformat(),
            }
            for m in conversation.messages
        ],
    }


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation = db.get(Conversation, conversation_id)
    if conversation is None or conversation.user_id != user.id:
        raise HTTPException(status_code=404, detail="Conversación no encontrada.")
    db.delete(conversation)
    db.commit()
    return None
