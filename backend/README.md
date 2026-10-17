# PonyArchive · Backend (FastAPI)

API REST que expone el agente RAG, la autenticación, la biblioteca y el Friendship Journal.

## Arranque

```powershell
pip install -r requirements.txt
copy ..\.env.example .\.env       # ajusta SECRET_KEY
python scripts/import_pony.py     # (re)construye la biblioteca: 808 docs / 813 fragmentos
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Documentación interactiva: <http://127.0.0.1:8000/docs> · Salud: `/health`.

## Módulos

| Ruta | Contenido |
|---|---|
| `app/agents/graph.py` | Grafo LangGraph: `validate_intent → retrieve → evaluate_sufficiency → generate → validate_answer → persist`, con salida a `catalog_query` o `reject` |
| `app/agents/state.py` | Estado compartido del grafo |
| `app/routers/` | `auth`, `chat`, `documents`, `journal`, `library`, `importer`, `health` |
| `app/services/ingestion.py` | Extracción, fragmentación (900/150), embeddings y metadatos |
| `app/services/vectorstore.py` | ChromaDB: búsqueda con filtros `doc_type`, `title`, `theme`, `user_id` |
| `app/services/llm.py` | `ChatOllama` (`reasoning=False`, `num_ctx=8192`) |
| `app/services/themes.py` | Taxonomía del Friendship Journal (reglas de palabras clave) |
| `app/security.py` | JWT local y validación Keycloak (JWKS) |

## Pruebas

```powershell
python scripts\smoke_test.py     # 11/11 (requiere el servidor arrancado)
```

## Datos

- `data/seed/fichas_narrativas.json` — 10 fichas de redacción propia (se siembran al arrancar).
- `data/ponyarchive.db` — SQLite (usuarios, documentos, conversaciones). **No se versiona.**
- `vectorstore/` — ChromaDB persistente. **No se versiona**; se regenera con `scripts/import_pony.py`.

Más información: `README.md` de la raíz y `../docs/decisiones.md`.
