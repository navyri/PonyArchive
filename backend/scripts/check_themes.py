"""Comprueba el filtro temático usando la función real de búsqueda."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.embeddings import embed_query
from app.services.vectorstore import get_collection, search

col = get_collection()
print("Fragmentos totales:", col.count())

consulta = "¿Qué episodios muestran el tema del trabajo en equipo?"
vec = embed_query(consulta)

sin_filtro = search(vec, k=5)
print("\nSin filtro temático:")
for r in sin_filtro:
    print(f"  {r['score']:.3f} {r['metadata'].get('title')} | themes={r['metadata'].get('themes')}")

con_filtro = search(vec, k=5, theme="trabajo en equipo")
print("\nCon filtro theme='trabajo en equipo':")
for r in con_filtro:
    print(f"  {r['score']:.3f} {r['metadata'].get('title')} | themes={r['metadata'].get('themes')}")
