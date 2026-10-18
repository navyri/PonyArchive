# PonyArchive

**Biblioteca inteligente de *My Little Pony: Friendship Is Magic* con un agente RAG (LangChain + LangGraph), modelo local en Ollama y una base vectorial propia.**

El agente responde preguntas sobre los 243 episodios y 555 personajes de la serie a partir de su propia base de conocimiento indexada, muestra las fuentes recuperadas con su similitud y **se niega a responder** cuando la evidencia no alcanza. Incluye autenticación con JWT, historial por usuario, carga de documentos y despliegue en la nube (0 USD).

Repositorio: https://github.com/navyri/PonyArchive

## Requisitos

| Componente | Versión | Notas |
|---|---|---|
| Python | 3.11+ | backend y agentes |
| Node.js | 20+ | frontend (Vite + React + TS) |
| Ollama | latest | modelo local `qwen3.5:4b` (también compatible con `llama3.2`) |

## Arranque rápido (local)

```bash
# 1. Backend
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env            # revisar EMBEDDINGS_PROVIDER=local, LLM_PROVIDER=ollama, VECTOR_PROVIDER=chroma
ollama serve &
ollama pull qwen3.5:4b
python -m uvicorn app.main:app --reload --port 8000

# 2. Frontend
cd frontend
npm install
npm run dev                     # http://localhost:5173
```

Al arrancar, el backend importa automáticamente los episodios y personajes desde [Pony API](https://github.com/PonyAPI/mlp-fim-api) y los enriquece con las sinopsis de la [wiki de Fandom](https://mlp.fandom.com) (CC BY-SA). La primera arrancada tarda ~3–5 min (importa 243 episodios + 555 personajes); posteriores lo omiten si ya están indexados.

## Características

| Característica | Estado | Detalle |
|---|---|---|
| Agente RAG con LangGraph | ✅ | Grafo con clasificación de intención, recuperación filtrada y respuesta fundamentada |
| Base vectorial | ✅ | Chroma local / Qdrant Cloud; embeddings e5-small (384d) u OpenAI |
| Respuestas con fuentes | ✅ | Cada respuesta lista los fragmentos con título, tipo y similitud |
| Anti-alucinación | ✅ | Umbral de similitud + rechazo literal cuando la evidencia no alcanza |
| Modelo local | ✅ | `qwen3.5:4b` vía Ollama |
| Autenticación JWT | ✅ | Registro, login, logout y refresh; historial por usuario |
| Carga de documentos | ✅ | Sube .txt/.md/.pdf y pregúntales al agente |
| Despliegue en la nube | ✅ | Frontend en Vercel y backend en Render (0 USD), pila dual por variable de entorno |

## Credenciales de prueba

Crea una cuenta desde la propia UI de registro. Hay un usuario de demostración en el seed:

| Campo | Valor |
|---|---|
| Email | `demo@ejemplo.com` |
| Contraseña | `pony123` |

## Estructura del proyecto

```
PonyArchive/
├── backend/
│   ├── app/
│   │   ├── routers/         # auth, chat, documents, library, importer, health
│   │   ├── services/        # embeddings, vectorstore, llm, pony_api, fandom, themes…
│   │   ├── agents/          # grafo LangGraph (graph.py, state.py)
│   │   ├── config.py        # ajustes y flags dual local/nube
│   │   ├── database.py      # SQLAlchemy (usuarios, conversaciones, documentos)
│   │   ├── models.py        # modelos ORM
│   │   ├── security.py      # JWT y hashing de contraseñas
│   │   ├── seed.py          # semilla de la biblioteca base
│   │   └── main.py          # composición de la API (FastAPI)
│   ├── scripts/             # smoke_test.py, e2e_compose.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/           # Chat, Documentos, Login
│   │   ├── components/      # Answer (fuentes desplegables)
│   │   ├── api.ts           # cliente HTTP tipado
│   │   └── index.css        # tema oscuro (paleta Starlight Glimmer)
│   └── vite.config.ts
├── docs/
│   ├── documento-tecnico.pdf # documento técnico
│   ├── presentacion.pdf      # láminas de la demo
│   ├── capturas/             # capturas de pantalla
│   ├── despliegue-nube.md    # checklist del despliegue (M8)
│   └── decisiones.md         # registro de decisiones
├── render.yaml               # blueprint del backend en Render
└── docker-compose.yml
```

## Endpoints

| Ruta | Contenido |
|---|---|
| `/health` | Estado del servicio, modelo y fragmentos indexados (sin auth) |
| `/docs` | Documentación OpenAPI/Swagger (sin auth) |
| `/api/auth/register` | Registro y creación de cuenta (sin token previo) |
| `/api/auth/login` | Login y emisión de token JWT |
| `/api/chat` | Consulta al agente RAG (con Bearer token) |
| `/api/chat/conversations` | Historial de conversaciones por usuario |
| `/api/documents` | Listado, subida y borrado de documentos (con token) |
| `/api/library/search` | Búsqueda en la biblioteca compartida |
| `/api/import/*` | Importación de Pony API (con token) |

## Despliegue en la nube (0 USD)

La arquitectura en nube usa **Frontend en Vercel + Backend en Render + Qdrant Cloud + OpenAI** (embeddings y chat). El frontend solo habla con el backend por `/api`; el modelo y la base vectorial quedan tras la API. Los tres providers se cambian por variable de entorno (`EMBEDDINGS_PROVIDER`, `LLM_PROVIDER`, `VECTOR_PROVIDER`); los valores por defecto son la pila local.

El paso a paso está en `docs/despliegue-nube.md` y las decisiones en `docs/decisiones.md`. El backend se publica con el blueprint `render.yaml` de la raíz; los secretos (`OPENAI_API_KEY`, `QDRANT_URL`, `QDRANT_API_KEY`) se cargan desde el panel de Render.

## Documentación y demo

El repositorio incluye el documento técnico y la presentación en `docs/`, además de una prueba e2e (`backend/scripts/e2e_compose.py`). La demo muestra el agente respondiendo con fuentes, el rechazo literal y la carga de documentos.

## Regenerar PDF

Los PDF se generan desde los HTML de `docs/` (impresión headless del navegador):

```bash
# desde la raíz del repositorio (Windows, Edge)
"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --headless --print-to-pdf="docs\documento-tecnico.pdf" --no-pdf-header-footer "file:///C:/ruta/al/repo/docs/documento-tecnico.html"
"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --headless --print-to-pdf="docs\presentacion.pdf" --no-pdf-header-footer "file:///C:/ruta/al/repo/docs/presentacion.html"
```
