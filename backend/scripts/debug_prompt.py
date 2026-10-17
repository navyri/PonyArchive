"""Reproduce la generación RAG aislando el prompt (sin grafo)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.graph import GENERATE_PROMPT, REFUSAL_MESSAGE, SUGGESTION, _context_blocks
from app.services.embeddings import embed_query
from app.services.llm import get_llm
from app.services.vectorstore import search

retrieved = search(embed_query("Compara Winter Wrap Up y Lesson Zero"), k=4)
prompt = GENERATE_PROMPT.format(
    refusal=REFUSAL_MESSAGE,
    suggestion=SUGGESTION,
    extra_rule="",
    context=_context_blocks(retrieved),
    question="Compara Winter Wrap Up y Lesson Zero: ¿en qué se diferencian?",
)
print("Longitud del prompt:", len(prompt), "caracteres")
print("Primeros 200:", prompt[:200].replace("\n", " | "))

msg = get_llm().invoke(prompt)
print("content tipo:", type(msg.content))
print("content longitud:", len(msg.content) if isinstance(msg.content, str) else "no-str")
print("content repr:", repr(msg.content)[:800])
