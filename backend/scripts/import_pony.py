"""Regenera la biblioteca completa: semilla + importación de Pony API.

Uso:  python scripts/import_pony.py
Borra antes los datos locales si se quiere una reconstrucción limpia.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal, init_db
from app.models import Document
from app.seed import seed_if_empty
from app.services.pony_api import import_characters, import_episodes, import_songs
from app.services.vectorstore import count_chunks

init_db()
db = SessionLocal()
try:
    t0 = time.time()
    semilla = seed_if_empty(db)
    print("Semilla:", semilla, f"({round(time.time() - t0, 1)}s)")

    t0 = time.time()
    episodios = import_episodes(db)
    print("Episodios:", episodios, f"({round(time.time() - t0, 1)}s)")

    t0 = time.time()
    personajes = import_characters(db)
    print("Personajes:", personajes, f"({round(time.time() - t0, 1)}s)")

    t0 = time.time()
    canciones = import_songs(db)
    print("Canciones:", canciones, f"({round(time.time() - t0, 1)}s)")

    print("TOTAL documentos:", db.query(Document).count())
    print("TOTAL fragmentos vectoriales:", count_chunks())
finally:
    db.close()
