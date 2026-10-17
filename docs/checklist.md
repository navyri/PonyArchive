# PonyArchive — Checklist maestro

> Convención: `[ ]` pendiente · `[~]` en progreso · `[x]` completado y verificado · `[!]` bloqueado · `[-]` fuera de alcance (con motivo)
>
> Regla: `[x]` solo con evidencia verificable. Si está generado pero sin probar: `[~]` + "implementado, pendiente de verificación".
> Los IDs NO se renumeran. Actualizado: 2026-10-17.

## FASE 0 — Requisitos y alcance

| ID | Estado | Evidencia | Pendiente o limitación |
|----|--------|-----------|------------------------|
| R01 | [x] | PDF "trabajo agente.pdf" leído: 10 páginas, 14.736 caracteres extraídos con pypdf → `Temp\opencode\trabajo_agente.txt` | — |
| R02 | [~] | Matriz creada en `docs/matriz-requisitos.md` | Pendiente revisión y aprobación |
| R03 | [~] | Alcance descrito en el prompt del proyecto | Pendiente aprobación explícita |
| R04 | [~] | Fichas narrativas creadas (10, redacción propia) y catálogo importado; continuidad única FIM | Etiquetas temáticas: clasificación propia, pendiente de revisar cobertura |
| R05 | [x] | HW/SO/herramientas verificados en terminal; presupuesto 0 USD, entrega individual, fecha: mañana, registrados en `docs/decisiones.md` | — |
| R06 | [~] | Estrategia definida: Ollama en portátil + túnel autenticado; backend Render free; frontend Vercel free | Pendiente de validación técnica (V01 ok local; falta P03 despliegue) |

## FASE 1 — Diseño y preparación

| ID | Estado | Evidencia | Pendiente o limitación |
|----|--------|-----------|------------------------|
| D01 | [x] | DEC-04 React+Vite+TS, DEC-05 Keycloak (con plan alternativo), DEC-06 Ollama, DEC-12 `qwen3.5:4b` + `multilingual-e5-small` + ChromaDB; dependencias instaladas y compatibles con Python 3.14 | Frontend aún no creado |
| D02 | [ ] | — | Arquitectura y diagrama sin crear |
| D03 | [x] | Modelo de datos en `backend/app/models.py` (User, Document, Chunk-free: fragmentos en Chroma, Conversation, Message) | — |
| D04 | [x] | Estado y nodos LangGraph en `backend/app/agents/state.py` y `graph.py` (validate_intent→retrieve→evaluate_sufficiency→generate/validate_answer/reject→catalog_query→persist) | — |
| D05 | [~] | Contratos recogidos en `docs/matriz-requisitos.md` (21 endpoints implementados y responden en `/docs`) | Falta revisar clasificación pública/privada con el profesor (R-04) |
| D06 | [ ] | — | Repositorio git sin crear (carpeta sin `.git`); estructura = Anexo A del PDF |
| D07 | [x] | `.env.example` en la raíz con todas las variables documentadas (sin secretos); `backend\.env` real local | — |

## FASE 2 — Viabilidad temprana

| ID | Estado | Evidencia | Pendiente o limitación |
|----|--------|-----------|------------------------|
| V01 | [x] | Ollama v0.40.5 instalado; `qwen3.5:4b` descargado y sirviendo (67 tok/s GPU RTX 4070); primera generación ~45 s, después 3–18 s | — |
| V02 | [x] | Embeddings `intfloat/multilingual-e5-small` (384 dims) ejecutados vía sentence-transformers | — |
| V03 | [x] | ChromaDB persistente conectada: 813 fragmentos indexados (808 documentos) en `backend\vectorstore` | — |
| V04 | [x] | RAG completo verificado con `smoke_test.py` → 11/11: recuperación, umbral y rechazo explícito | — |
| V05 | [ ] | — | — |
| V06 | [ ] | — | — |
| V07 | [ ] | — | — |

## FASE 3 — Autenticación y backend

| ID | Estado | Evidencia | Pendiente o limitación |
|----|--------|-----------|------------------------|
| B01 | [ ] | — | Keycloak no instalado (DEC-05); modo `local` JWT activo como plan alternativo documentado en `docs/decisiones.md` §4 |
| B02 | [x] | Registro/login/refresh/logout/me en `backend/app/routers/auth.py`; register → 201 y token JWT verificado en smoke | — |
| B03 | [x] | `GET /api/chat` sin token → 401 verificado en smoke | — |
| B04 | [x] | Historial por usuario: `GET /api/chat/conversations` devuelve solo las del usuario (verificado en smoke, caso B04) | — |
| B05 | [x] | Aislamiento de documentos entre usuarios verificado en smoke (T10): el usuario no ve cargas ajenas (`visible_to`/`user_id` en filtros) | — |
| B06 | [x] | FastAPI con 21 endpoints operativos; `GET /health` responde estado, modelo, auth_provider y chunks indexados | — |

## FASE 4 — Datos y documentos

| ID | Estado | Evidencia | Pendiente o limitación |
|----|--------|-----------|------------------------|
| K01 | [x] | `GET /v1/episode/all` → 243 · `/character/all` → 555 · `/song/all` → 192 · HTTP 200 · CORS `*` · SQLite 999 KB disponible | — |
| K02 | [~] | Datos CC BY-SA 3.0, código MIT; último update 2020-04-30; path con `%20` → 403 (usar IDs o `_`); sin campos narrativos | Falta decidir y documentar atribución en README |
| K03 | [x] | Cliente `backend/app/services/pony_api.py` con reintentos y paginación | — |
| K04 | [x] | Normalización e importación funcionando: `python scripts\import_pony.py` → 243 episodios + 555 personajes indexados sin duplicados (2ª ejecución: 798 omitidos) | — |
| K05 | [x] | Fragmentación en `services/ingestion.py` (813 fragmentos, deduplicación por `content_hash`) | — |
| K06 | [x] | **Campos narrativos NO existen en la API**: 10 fichas narrativas propias creadas en `backend/data/seed/fichas_narrativas.json` y sembradas | — |
| K07 | [x] | Carga de documentos (`POST /api/documents`, txt/md) → 201 e indexado; verificado en smoke (T07/K07) | — |
| K08 | [x] | Biblioteca consultable: `GET /api/library` con filtros tipo/título/tema y paginación | — |
| K09 | [~] | Endpoint `POST /api/import/pony` para reimportar desde la API | No incluido en smoke test |
| K10 | [x] | Borrado de documentos verificado en navegador: `DELETE /api/documents/{id}` → 204, fila eliminada y mensaje "Documento ... eliminado" | Decisión K12 (alcance) sigue pendiente de confirmación |
| K11 | [ ] | — | — |
| K12 | [~] | Borrado implementado a nivel endpoint | Decisión pendiente: ¿eliminación de documentos en alcance? |

## FASE 5 — Agente RAG

| ID | Estado | Evidencia | Pendiente o limitación |
|----|--------|-----------|------------------------|
| A01 | [x] | Grafo LangGraph funcional en `backend/app/agents/graph.py`; probado por los 10 casos del smoke | — |
| A02 | [x] | Recuperación vectorial con metadatos (doc_type, tema, usuario) en `services/vectorstore.py` | — |
| A03 | [x] | Prompt restringido al contexto en `graph.py` (E3) | — |
| A04 | [x] | Rechazo con frase literal exigida por §4 del PDF: "No tengo suficiente información en mi base de conocimiento para responder esa pregunta." (T04 y T05 del smoke) | — |
| A05 | [x] | Fuentes devueltas con cada respuesta (título, tipo, similitud) y mostradas en el smoke (T01, T07) | — |
| A06 | [x] | Persistencia de conversaciones por usuario (`persist` del grafo) | — |
| A07 | [x] | **≥2 estrategias anti-alucinación (§3.4)**: 7 implementadas (E1 umbral 0.62, E2 nodo de suficiencia, E3 prompt restringido, E4 rechazo literal, E5 fuentes obligatorias, E6 verificación de entidades, E7 conteos por SQL) — ver `docs/decisiones.md` | — |
| A08 | [~] | Clasificación de intención (RAG vs. consulta de catálogo) en `validate_intent`/`catalog_query` | Cobertura de categorías sin test sistemático |
| A09 | [x] | Friendship Journal implementado y **verificado**: `backend/app/routers/journal.py` (temas, comparación, consultas) + UI `JournalPage.tsx`; probado en navegador (tema "amistad" y comparación Twilight/Rainbow, 200 con fuentes) | — |
| A10 | [x] | Comparación de episodios/personajes verificada en navegador y por API (`/api/journal/compare` → 200) | — |
| A11 | [ ] | — | Mejora opcional (no la exige el PDF) |

## FASE 6 — Frontend

| ID | Estado | Evidencia | Pendiente o limitación |
|----|--------|-----------|------------------------|
| F01 | [x] | Proyecto creado con `npm create vite@latest frontend -- --template react-ts` en `frontend/`; `npm run build` (tsc + vite) sin errores | — |
| F02 | [x] | Login/registro/logout en `frontend/src/pages/LoginPage.tsx` + `src/auth.tsx`; verificado en navegador: registro 201, error 422 mostrado (dominio `.test` rechazado), login y logout (token borrado, redirect a `/login`) | — |
| F03 | [x] | Chat en `frontend/src/pages/ChatPage.tsx`: respuestas con fuentes (título, tipo, similitud), rechazo con etiqueta "Sin evidencia suficiente" y frase literal, estado de carga y sugerencias; verificado en navegador (T01, T04 y pregunta sobre doc propio) | — |
| F04 | [x] | `frontend/src/pages/DocumentsPage.tsx`: subida (.txt/.md), listado con pestañas (Todos/Biblioteca/Míos) y filtro por título, borrado con confirmación; verificado en navegador (201 al subir, fila con "Tuyo", borrado con mensaje) | — |
| F05 | [x] | Historial en la barra lateral del chat: lista, apertura de conversación y borrado; verificado en navegador (9 conversaciones, apertura carga los mensajes) | — |
| F06 | [ ] | — | — |
| F07 | [x] | Friendship Journal en `frontend/src/pages/JournalPage.tsx`: temas (11), consulta temática y comparación; verificado en navegador (POST 200, respuestas con fuentes) | — |
| F08 | [ ] | — | — |

## FASE 7 — Pruebas integrales

| ID | Estado | Evidencia | Pendiente o limitación |
|----|--------|-----------|------------------------|
| T01–T10, T10b, B04 | [x] | `python scripts\smoke_test.py` → **11/11 OK** (2026-10-17): health, register, 401, T01 factual con fuentes, T04 rechazo fuera de dominio, T05 sin evidencia, historial B04, K07 carga, T07 pregunta sobre doc cargado, T10 aislamiento de recuperación, T10b aislamiento de listado | — |
| T11–T12 y pruebas de rendimiento/carga | [ ] | — | Sin iniciar |

## FASE 8 — Despliegue

| ID | Estado | Evidencia | Pendiente o limitación |
|----|--------|-----------|------------------------|
| P01–P07 | [ ] | — | Sin iniciar. Presupuesto aprobado: 0 USD |

## FASE 9 — Entregables

| ID | Estado | Evidencia | Pendiente o limitación |
|----|--------|-----------|------------------------|
| E01–E09 | [ ] | — | Sin iniciar (repo GitHub, doc técnico PDF, diapositivas 8–12, guion de demo) |

---

## Resumen de estado (2026-10-17, tras smoke 11/11 y verificación de la interfaz en navegador)

- `[x]`: R01, R05, D01, D03, D04, D07, V01–V04, B02–B06, K01, K03–K08, K10, A01–A07, A09, A10, F01–F05, F07, T01–T10/T10b/B04 (42)
- `[~]`: R02, R03, R04, R06, D05, K02, K09, K12, A08 (9)
- `[!]`: ninguno
- `[ ]`: D02, D06, V05–V07, B01, K11, A11, F06, F08, T11–T12, P01–P07, E01–E09 (22 aprox.)

### Bloqueos y decisiones abiertas
1. **B01/Keycloak** (DEC-05): probar Docker con daemon encendido; si los free tiers no lo sostienen → plan alternativo JWT (ya operativo en modo `local`).
2. **R-04**: tensión "ningún endpoint sin autenticación" vs. `/health`, `OPTIONS`, `/api/auth/*` → consulta al profesor.
3. **K12**: ¿alcance de la eliminación de documentos?
