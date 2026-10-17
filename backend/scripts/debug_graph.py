"""Evaluación del grafo con preguntas de prueba (T01–T06).

Se ejecuta directamente contra el grafo, sin servidor:
    python scripts/debug_graph.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # permite ejecutar desde backend/

from app.agents.graph import build_graph

PREGUNTAS = [
    ("T01 factual con respuesta en la biblioteca", "¿Quién es Twilight Sparkle?"),
    ("T02 consulta temática", "¿Qué episodios muestran el tema del trabajo en equipo?"),
    ("T03 comparación entre documentos", "Compara Winter Wrap Up y Lesson Zero: ¿en qué se diferencian?"),
    ("T04 pregunta fuera del dominio", "¿Cuál es la mejor receta para preparar sushi?"),
    ("T05 dentro del dominio sin evidencia", "¿Qué personaje secundario aparece en el capítulo 47 con un sombrero morado?"),
    ("T06 consulta de conteo/catálogo", "¿Cuántos episodios hay documentados en la biblioteca?"),
]

graph = build_graph()
print("=" * 78)
for etiqueta, pregunta in PREGUNTAS:
    t0 = time.time()
    final = graph.invoke({"question": pregunta, "user_id": 1, "conversation_id": 0, "history": []})
    dt = round(time.time() - t0, 1)
    print(f"\n### {etiqueta}  ({dt}s)")
    print(f"PREGUNTA: {pregunta}")
    print(f"intent={final.get('intent')} | theme={final.get('theme')} | suficiente={final.get('sufficient')}")
    print(f"fragmentos={len(final.get('retrieved', []))} | rechazada={final.get('refused')} | grounded={final.get('grounded')}")
    if final.get("refusal_reason"):
        print(f"razón rechazo: {final['refusal_reason']}")
    if final.get("retrieval_notes"):
        print(f"notas: {final['retrieval_notes']}")
    for s in final.get("sources", [])[:3]:
        print(f"  fuente: {s['title']} ({s['doc_type']}, similitud {s['score']})")
    print(f"RESPUESTA:\n{(final.get('answer') or '')[:600]}")
    print("-" * 78)
