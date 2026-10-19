<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&height=140&color=21182E&text=PONYARCHIVE%20%C2%B7%20BACKEND&fontColor=B78ADC&fontSize=38&fontAlignY=34&desc=API%20REST%20%C2%B7%20agente%20RAG%20%C2%B7%20LangGraph&descColor=79D9CD&descAlignY=60"/>
</p>

<p align="center">
  <img src="https://64.media.tumblr.com/ca492f2e341e5f0d825c899842bd2ca3/f8c0a52918cf3b90-85/s500x750/044bc7e22b528a519ee7391eeb1533b5542503dc.gifv" alt="Twilight Sparkle" height="200"/>
</p>

<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=rect&height=6&color=21182E"/>
</p>

API REST que expone el agente RAG, la autenticación, la biblioteca documental y el historial por usuario.


## Puesta en marcha

```bash
pip install -r requirements.txt
ollama serve &
python -m uvicorn app.main:app --reload --port 8000
```

Swagger: http://localhost:8000/docs

<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=rect&height=6&color=21182E"/>
</p>

## Estructura

| Ruta | Contenido |
|---|---|
| `app/main.py` | Composición de la API (FastAPI) |
| `app/config.py` | Ajustes (pydantic-settings) y flags dual local/nube |
| `app/database.py` | SQLAlchemy: motor, sesión y creación de tablas |
| `app/models.py` | Modelos ORM: User, Conversation, Message, Document |
| `app/routers/` | `auth`, `chat`, `documents`, `library`, `importer`, `health` |
| `app/agents/graph.py` | Grafo de LangGraph: clasificación, recuperación, respuesta y rechazo |
| `app/agents/state.py` | Estado tipado del grafo |
| `app/services/embeddings.py` | Embeddings (e5-small local u OpenAI) |
| `app/services/vectorstore.py` | Base vectorial (Chroma local o Qdrant Cloud) |
| `app/services/llm.py` | LLM (Ollama local u OpenAI) |
| `app/services/pony_api.py` | Importador de Pony API (episodios y personajes) |
| `app/services/fandom.py` | Sinopsis de episodios desde la wiki de Fandom (CC BY-SA) |
| `app/services/themes.py` | Taxonomía temática (etiquetas de recuperación por palabras clave) |
| `app/services/ingestion.py` | Troceado e indexación de documentos |
| `app/security.py` | JWT y hashing |
| `app/seed.py` | Semilla de la biblioteca base |
| `scripts/smoke_test.py` | 12 pruebas de API contra el backend local |
| `scripts/e2e_compose.py` | Prueba end-to-end contra el stack de Docker |

<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=rect&height=6&color=21182E"/>
</p>

## Pruebas

```bash
python scripts/smoke_test.py          # 12 pruebas
python scripts/e2e_compose.py         # end-to-end (docker compose up -d antes)
```
<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=rect&height=6&color=21182E"/>
</p>

## Configuración dual local/nube

| Variable | Local | Nube |
|---|---|---|
| `EMBEDDINGS_PROVIDER` | `local` (e5-small) | `openai` |
| `LLM_PROVIDER` | `ollama` | `openai` |
| `VECTOR_PROVIDER` | `chroma` | `qdrant` |

Los secretos (`OPENAI_API_KEY`, `QDRANT_URL`, `QDRANT_API_KEY`, `JWT_SECRET`) van en `.env` o en las variables de entorno del proveedor; nunca en el repositorio.

<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&height=120&section=footer&color=21182E" alt=""/>
</p>
