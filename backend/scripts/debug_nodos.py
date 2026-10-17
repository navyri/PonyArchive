"""Ejecuta los nodos del grafo uno a uno para localizar dónde se pierde la respuesta."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents import graph as g

state = {
    "question": "Compara Winter Wrap Up y Lesson Zero: ¿en qué se diferencian?",
    "user_id": 1,
    "conversation_id": 0,
    "history": [],
}

print(">> validate_intent")
state.update(g.validate_intent(state))
print({k: state.get(k) for k in ("intent", "theme", "title_filter", "doc_type_filter", "compare_items")})

print(">> retrieve")
state.update(g.retrieve(state))
print("recuperados:", len(state["retrieved"]), "| notas:", state["retrieval_notes"])

print(">> evaluate_sufficiency")
state.update(g.evaluate_sufficiency(state))
print("sufficient:", state.get("sufficient"), "| reason:", state.get("refusal_reason"))

print(">> generate")
salida = g.generate(state)
print("claves devueltas:", list(salida.keys()))
print("longitud answer:", len(salida.get("answer", "")))
print("answer repr:", repr(salida.get("answer"))[:400])
state.update(salida)

print(">> validate_answer")
state.update(g.validate_answer(state))
print("grounded:", state.get("grounded"))
