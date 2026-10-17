"""Depura la prueba T07: documento subido por el usuario y pregunta sobre él."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models import Document
from app.services.embeddings import embed_query
from app.services.vectorstore import get_collection, search

col = get_collection()
db = SessionLocal()
try:
    doc = db.query(Document).filter(Document.source == "upload").order_by(Document.id.desc()).first()
    print("Último documento subido:", doc.id, doc.title, "| status:", doc.status, "| user_id:", doc.user_id, "| chunks:", doc.chunk_count)
finally:
    db.close()

consulta = "¿De qué se ocupa la cebra Zecora según el archivo de prueba?"
vec = embed_query(consulta)

general = search(vec, k=8)
print("\nBúsqueda general (top 8):")
for r in general:
    print(f"  {r['score']:.3f} {r['metadata'].get('title')} (user_id={r['metadata'].get('user_id')})")

if doc:
    propios = search(vec, k=8, user_id=doc.user_id)
    print(f"\nBúsqueda con filtro user_id={doc.user_id}:")
    for r in propios:
        print(f"  {r['score']:.3f} {r['metadata'].get('title')}")

    # Comprobación cruda en Chroma del mismo filtro
    crudo = col.get(where={"user_id": doc.user_id}, limit=5)
    print(f"\nChroma get(where user_id={doc.user_id}):", len(crudo["ids"]), "fragmento(s)")
    for m in crudo["metadatas"][:3]:
        print("  -", m.get("title"), "| user_id:", repr(m.get("user_id")), type(m.get("user_id")).__name__)
