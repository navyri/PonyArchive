"""Ejecuta el grafo con la pregunta de T07 para ver por qué se rechaza."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.graph import build_graph

graph = build_graph()
for user_id in (3, 1):
    final = graph.invoke(
        {
            "question": "¿De qué se ocupa la cebra Zecora según el archivo de prueba?",
            "user_id": user_id,
            "conversation_id": 0,
            "history": [],
        }
    )
    print(f"\n=== user_id={user_id} ===")
    print("intent:", final.get("intent"), "| titulo:", final.get("title_filter"), "| tipo:", final.get("doc_type_filter"))
    print("fragmentos:", len(final.get("retrieved", [])), "| suficiente:", final.get("sufficient"), "| rechazada:", final.get("refused"))
    print("notas:", final.get("retrieval_notes"))
    for r in final.get("retrieved", [])[:4]:
        print(f"  {r['score']:.3f} {r['metadata'].get('title')}")
    print("RESPUESTA:", (final.get("answer") or "")[:250])
