# PonyArchive ★

**Biblioteca inteligente de *My Little Pony: Friendship Is Magic* con un agente RAG (LangChain + LangGraph), modelo local en Ollama y una función especial: Friendship Journal.**

PonyArchive responde preguntas sobre la serie **usando exclusivamente documentos indexados** (episodios, personajes, fichas narrativas propias y archivos subidos por cada usuario). Cuando no hay evidencia suficiente, **rechaza explícitamente** en lugar de inventar:

> No tengo suficiente información en mi base de conocimiento para responder esa pregunta.

---

## Contenidos

- [Qué incluye](#qué-incluye)
- [Estructura del repositorio](#estructura-del-repositorio)
- [Requisitos previos](#requisitos-previos)
- [Puesta en marcha local](#puesta-en-marcha-local)
- [Pruebas](#pruebas)
- [Estrategias anti-alucinación](#estrategias-anti-alucinación)
- [Configuración (.env)](#configuración-env)
- [Autenticación](#autenticación)
- [Documentación y decisiones](#documentación-y-decisiones)
- [Atribuciones y licencias](#atribuciones-y-licencias)

---

## Qué incluye

| Requisito (§6.1) | Estado | Dónde está |
|---|---|---|
| Backend + frontend funcionales | ✅ | `backend/` (FastAPI, 21 endpoints) · `frontend/` (React + Vite + TS) |
| Autenticación y autorización | ✅ | JWT con registro/login/refresh/logout; aislamiento por usuario |
| Agente con LangChain/LangGraph | ✅ | `backend/app/agents/graph.py` (grafo con 9 nodos) |
| Modelo local | ✅ | Ollama `qwen3.5:4b` (GPU) · embeddings `multilingual-e5-small` |
| Base vectorial + carga de documentos | ✅ | ChromaDB persistente · `POST /api/documents` (.txt/.md) |
| Respuestas fundamentadas en el contexto | ✅ | Fuentes con título, tipo y similitud en cada respuesta |
| Rechazo explícito | ✅ | Frase literal + registro del motivo de rechazo |
| Historial por usuario | ✅ | Conversaciones privadas (`/api/chat/conversations`) |
| Friendship Journal | ✅ | Consultas por tema y comparaciones (`/api/journal`) |

**Flujo del agente** (nodos del grafo):

```
pregunta → validate_intent → retrieve → evaluate_sufficiency
                                      ↘ catalog_query (conteos por SQL)
        → generate → validate_answer → persist
                    ↘ reject (rechazo literal con motivo)
```

---

## Estructura del repositorio

Sigue el **Anexo A** del enunciado:

```
MLP-Agente/
├── backend/
│   ├── app/
│   │   ├── agents/          # grafo LangGraph (graph.py, state.py)
│   │   ├── routers/         # endpoints (auth, chat, documents, journal, library…)
│   │   ├── services/        # ingestion, vectorstore, llm, embeddings, pony_api, themes
│   │   ├── config.py        # ajustes por entorno (.env)
│   │   ├── main.py          # FastAPI + CORS + semilla
│   │   ├── models.py        # SQLAlchemy: User, Document, Conversation, Message
│   │   └── security.py      # JWT local + modo Keycloak (JWKS)
│   ├── scripts/
│   │   ├── smoke_test.py    # 11 pruebas integradas (ver más abajo)
│   │   └── import_pony.py   # (re)construye la biblioteca desde Pony API
│   ├── data/seed/           # fichas narrativas propias (redacción del equipo)
│   ├── vectorstore/         # ChromaDB persistente (no se versiona; se regenera)
│   ├── requirements.txt
│   └── .env                 # secretos locales (no se versiona; ver .env.example)
├── frontend/
│   ├── src/
│   │   ├── pages/           # Chat, Documentos, Friendship Journal, Login
│   │   ├── components/      # fuentes y formato de respuesta
│   │   ├── api.ts           # cliente HTTP con refresh de token
│   │   └── auth.tsx         # sesión (JWT en localStorage)
│   ├── public/
│   └── package.json
├── docs/
│   ├── checklist.md         # checklist maestro con IDs estables
│   ├── decisiones.md        # decisiones, riesgos y pruebas realizadas
│   └── matriz-requisitos.md # requisito → componente → prueba → evidencia
├── .env.example
└── README.md
```

---

## Requisitos previos

- **Python 3.14** (probado) con `pip`
- **Node.js 24** (probado)
- **Ollama** (probado con v0.40.5): <https://ollama.com>
- GPU recomendada (el modelo 4B usa ~5 GB VRAM); funciona también en CPU, más lento.

---

## Puesta en marcha local

### 1. Modelo local (Ollama)

```powershell
ollama pull qwen3.5:4b          # modelo principal (DEC-12)
```

> Los embeddings **no** se piden a Ollama: se generan con `sentence-transformers`
> (`intfloat/multilingual-e5-small`, 384 dimensiones) dentro del backend.

### 2. Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate        # o: source .venv/bin/activate
pip install -r requirements.txt
copy ..\.env.example .\.env     # o: cp ../.env.example ./.env  (ajusta SECRET_KEY)
python scripts/import_pony.py   # ~1 min: 808 documentos y 813 fragmentos
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

- API y documentación interactiva: <http://127.0.0.1:8000/docs>
- Salud del servicio: <http://127.0.0.1:8000/health>
- La primera respuesta del modelo tarda ~45 s (carga); después, 3–18 s por pregunta.

### 3. Frontend

```powershell
cd frontend
npm install
npm run dev        # http://localhost:5173
```

El frontend habla con el backend en `VITE_API_URL` (por defecto `http://127.0.0.1:8000`);
el CORS del backend ya permite `http://localhost:5173`.

---

## Pruebas

```powershell
# con el servidor arrancado
python scripts\smoke_test.py
```

Última ejecución (2026-10-17): **11/11 OK**

| Caso | Qué comprueba |
|---|---|
| health | servicio arriba y fragmentos indexados |
| register / 401 | registro con token y rechazo sin autenticación |
| T01 | respuesta factual con **fuentes y similitud** |
| T04 | rechazo literal fuera de dominio |
| T05 | rechazo sin evidencia suficiente (umbral) |
| B04 | historial aislado por usuario |
| K07/T07 | subir un documento y **preguntar por su contenido** |
| T10 | la recuperación no devuelve documentos ajenos |
| T10b | el **listado** tampoco muestra documentos ajenos |

---

## Estrategias anti-alucinación

Mínimo exigido: 2 · Implementadas: **7** (detalle en `docs/decisiones.md`).

1. **E1 · Umbral de similitud** (0.62): los fragmentos por debajo se descartan y se anota el motivo.
2. **E2 · Nodo de suficiencia**: `evaluate_sufficiency` decide si el contexto permite responder.
3. **E3 · Prompt restringido**: "usa SOLO los fragmentos [Documento N]; no uses tu conocimiento previo".
4. **E4 · Rechazo literal**: frase exacta exigida por el enunciado, más el motivo interno.
5. **E5 · Fuentes obligatorias**: título, tipo y similitud de cada fragmento usado.
6. **E6 · Verificación de entidades**: si la respuesta cita algo ausente del contexto, se reintenta y, si persiste, se rechaza.
7. **E7 · Conteos por SQL**: las preguntas de "¿cuántos…?" se resuelven contra la base, nunca por similitud.

---

## Configuración (.env)

Copia `.env.example` a `backend/.env`. Variables principales:

| Variable | Descripción | Por defecto |
|---|---|---|
| `SECRET_KEY` | clave de los JWT (**obligatoria en producción**, ≥32 bytes) | `cambiar-en-produccion` |
| `AUTH_PROVIDER` | `local` (JWT propio) o `keycloak` | `local` |
| `OLLAMA_BASE_URL` / `OLLAMA_MODEL` | endpoint y modelo | `http://localhost:11434` / `qwen3.5:4b` |
| `SIMILARITY_THRESHOLD` | umbral anti-alucinación (E1) | `0.62` |
| `CORS_ORIGINS` | orígenes permitidos, separados por coma | `http://localhost:5173,...` |
| `VITE_API_URL` (en `frontend/.env`) | URL base de la API para el navegador | `http://127.0.0.1:8000` |

---

## Autenticación

- **Modo actual (`AUTH_PROVIDER=local`)**: JWT propio (access 60 min + refresh 7 días),
  bcrypt para las contraseñas, y todas las rutas de negocio exigen `Bearer`.
- **Modo `keycloak` (DEC-05, en preparación)**: el backend ya valida tokens por JWKS
  (`backend/app/security.py`); ver `docs/decisiones.md` §4 para el plan y sus riesgos (R-03).

Clasificación de rutas (revisión pendiente con el profesor, riesgo R-04): ver
`docs/matriz-requisitos.md` §7 — `/health` y `/api/auth/*` no exigen token previo; el resto sí.

---

## Documentación y decisiones

| Archivo | Contenido |
|---|---|
| `docs/checklist.md` | checklist maestro con IDs estables (R/K/A/F/T/P/E) y su evidencia |
| `docs/decisiones.md` | decisiones (DEC-01…12), riesgos (R-01…08), plan de auth alternativo y **todas las pruebas realizadas** |
| `docs/matriz-requisitos.md` | requisito → componente → prueba → evidencia |

---

## Atribuciones y licencias

- **Código**: MIT (ver `LICENSE`).
- **Datos de Pony API** (`<https://ponyapi.net>`): **CC BY-SA 3.0** — atribución obligatoria,
  también visible en la app (columna "Origen" y enlaces de cada documento).
- **Fichas narrativas** (`backend/data/seed/fichas_narrativas.json`): redacción propia del equipo,
  basada en los datos anteriores.
- **Etiquetas temáticas**: regla determinista de palabras clave (`backend/app/services/themes.py`),
  no una valoración del modelo.
- *My Little Pony: Friendship Is Magic* es una obra de Hasbro. Este proyecto es un
  **trabajo académico de aficionados** sin ánimo de lucro.
