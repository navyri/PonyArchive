# PonyArchive — Registro de decisiones, bloqueos, riesgos y pruebas

Actualizado: 2026-10-18 (Fases 0–8: backend + agente + frontend + Docker operativos, smoke 12/12, Journal retirado, correcciones del agente verificadas y entregables `docs/` regenerados)

## 1. Decisiones

| ID | Decisión | Estado | Motivo | Alternativas descartadas |
|----|----------|--------|--------|--------------------------|
| DEC-01 | Trabajo **individual** | [D] aprobada | Respuesta del equipo | Trabajo en pareja |
| DEC-02 | Fecha de entrega: **2026-10-18 (mañana)** | [D] dato fijado | Respuesta del equipo | — |
| DEC-03 | Presupuesto de despliegue: **0 USD** (solo free tiers) | [D] aprobada | Respuesta del equipo | Plan de pago, VM con GPU (5–15 USD/mes) |
| DEC-04 | Frontend: **React + Vite + TypeScript** | [D] aprobada | Más ligero; un solo backend que desplegar | Next.js (SSR innecesario) |
| DEC-05 | Autenticación: **Keycloak en Docker** | [D] aprobada **con riesgo R-03**; **superada** → ver R-03 y §4 (opción 3: JWT propio operativo, Keycloak como flag) | Elección explícita del equipo; el PDF lo recomienda | JWT propio (más simple con 0 USD), Supabase Auth |
| DEC-06 | Modelo: **Ollama en el portátil + túnel autenticado** hacia el backend en la nube | [D] aprobada | Coste 0 USD; demo presencial; RTX 4070 disponible | VM con GPU en la nube, modelo en CPU remoto |
| DEC-07 | Backend: **FastAPI** | [D] decidida | Encaja con LangChain (Python); implementado en `backend/app` (21 endpoints) | NestJS, Flask, Django |
| DEC-08 | Base vectorial: **ChromaDB** persistente en disco | [D] decidida | Nativa de Python, sin servicio externo (0 USD); 813 fragmentos indexados | FAISS, Qdrant, pgvector |
| DEC-09 | Embeddings: **`intfloat/multilingual-e5-small`** (384 dims, sentence-transformers) | [D] decidida | Rendimiento correcto en español; instalado y ejecutado en local | Embeddings de Ollama (poco multilingües) |
| DEC-10 | Fichas narrativas y etiquetas temáticas: **redacción propia**, no proceden de la API | [D] derivada de la verificación K01 | La API no tiene campos narrativos; la wiki solo aparece como enlace | Scraping de mlp.fandom.com (fuera de alcance y de condiciones) |
| DEC-11 | Continuidad única: **My Little Pony: Friendship Is Magic** | [D] decidida | Adecuado al alcance MVP; biblioteca importada completa (243 episodios, 555 personajes, 10 fichas) | Otras generaciones (fuera de alcance) |
| DEC-12 | Modelo LLM: **`qwen3.5:4b`** con `reasoning=False` y `num_ctx=8192`; respaldo `qwen2.5:3b` | [D] decidida | 67 tok/s en la RTX 4070; primeras pruebas con razonamiento vaciaban la respuesta (corregido) | `qwen2.5:7b` (no cabe bien en 8 GB VRAM) |
| DEC-13 | Interfaz en **tema oscuro mágico** (paleta de noche con brillos aqua, derivada de la paleta Starlight Glimmer) | [D] decidida | Petición explícita del equipo; no usa la palabra "vtuber" en la IU | Tema claro (menos legible en la demo), tema por usuario (fuera de alcance) |
| DEC-14 | **Notas de contexto del curso** indexadas como `doc_type="nota_curso"` (`backend/data/seed/contexto_curso.json`, semilla idempotente `seed_contexto()`) | [D] decidida | El profesor exige que el agente responda con fundamento preguntas de contexto del aula (p. ej. Duvan Gomez); la evidencia de dominio en `evaluate_sufficiency` acepta `upload` o `nota_curso` | Hardcodear la respuesta (alucinación encubierta), subirla como documento de usuario (no visible a todos) |
| DEC-15 | **Docker**: backend `python:3.12-slim` con el modelo de embeddings horneado, frontend `node → nginx` con proxy, `docker-compose.yml` en la raíz (puertos 8010/8081 por estar 5173/8080 ocupados) | [D] decidida | Requisito Anexo A; reproduce el despliegue en un solo comando | Solo imágenes oficiales (el modelo e5-small pesa poco y evita una descarga en cada arranque) |
| DEC-16 | La semilla (`data/seed`) se copia a **`/app/seed`, fuera del volumen de datos** (`PONYARCHIVE_SEED_DIR`) | [D] decidida | `docker-compose` monta un volumen en `/app/data` y enmascararía la semilla de la imagen (bug reproducido: `seed_contexto` devolvía `sin_notas`) | Recrear el volumen en cada arranque (perdería la biblioteca importada) |
| DEC-17 | **Despliegue en nube**: Qdrant Cloud + OpenAI (embeddings y LLM), frontend en Vercel y backend en Render (free tiers); flags duales `EMBEDDINGS_PROVIDER` / `LLM_PROVIDER` / `VECTOR_PROVIDER` para conmutar local↔nube sin tocar código | [D] aprobada por el equipo | 0 USD (DEC-03) y sin GPU propia en la nube; los flags permiten demostrar ambas configuraciones | VM con GPU (5–15 USD/mes), Ollama por túnel (latencia frágil en la demo) |
| DEC-18 | **Retirada de Friendship Journal** (temas y comparación de personajes) | [D] decidida | La función quedaba sin uso tras centrar el alcance en el chat RAG; se eliminan su UI, endpoints y lógica del agente (DEC-09 queda superada). Se conservan `themes.py`, el campo `theme` y el intent `comparacion` por si se retoman | Mantener la funcionalidad a medias (UI sin backend), dejarla oculta (código muerto en el repo, §1.2) |
| DEC-19 | **Correcciones del agente tras revisión**: (1) el spinner de consulta solo aparece en la conversación activa; (2) las preguntas de temporadas/capítulos devuelven el desglose real (9 temporadas, 221 capítulos numerados + 22 especiales) vía `fetch_documents()` y no el conteo de tipos; (3) "¿qué preguntas puedes contestar?" se detecta de forma determinista (intent `meta`, patrones `META_PATTERNS`) y responde con el alcance fijo G4 sin invocar al LLM ni recuperar | [D] decidida | Tres fallos reportados en la demo de prueba; el intent `meta` evita que el LLM improvise una respuesta sobre su propio alcance | Responder con el LLM (no determinista), un único endpoint de catálogo (el desglose vive en el grafo) |

## 2. Bloqueos

Ninguno activo a 2026-10-18. Pendientes externos: credenciales de nube (M8) y consulta al profesor sobre R-04.

## 3. Riesgos y deuda técnica

| ID | Riesgo | Evidencia | Intentos / estado | Impacto | Acción |
|----|--------|-----------|-------------------|---------|--------|
| R-01 | **Entrega en 24 h** con un solo equipo | Respuesta del equipo | — | Crítico: hay que priorizar requisitos mínimos (§6.1) sobre pulido | Camino crítico: modelo → RAG → auth → chat → despliegue |
| R-02 | Python 3.14 muy nuevo para el ecosistema ML | Instalado Python 3.14.2 | Instalación real completa: langgraph, chromadb, sentence-transformers, fastapi; backend funcionando y smoke 10/10 | **Resuelto** | Mantener versions fijadas en `requirements.txt` |
| R-03 | **Keycloak con 0 USD y fecha corta**: necesita contenedor con ~512 MB+ y, en producción, un alojamiento que los free tiers suelen no cubrir | PDF §2.1 lo permite con otra solución; elección del equipo | Resuelto aplicando el **plan alternativo §4 (opción 3)**: JWT propio operativo de extremo a extremo (`AUTH_PROVIDER=local`); Keycloak queda implementado como flag (`security.py` `_decode_keycloak` + JWKS) sin desplegar | Bajo: la auth desplegada no depende de Keycloak | Documentar en el doc técnico §auth; flag disponible si se retoma |
| R-04 | Interpretación literal de "ningún endpoint sin autenticación" vs. rutas técnicas (OPTIONS, /health, login) | PDF §2.1 | Clasificación en 3 grupos propuesta en `matriz-requisitos.md` §7 | Medio: posible observación del evaluador | Consultar al profesor / documentar abiertamente |
| R-05 | Posible conflicto `huggingface_hub` entre chromadb (≥2.x) y sentence-transformers (1.x) | Dry-runs separados mostraron versiones incompatibles | Instalación conjunta realizada y verificada: embeddings y ChromaDB operativos a la vez | **Resuelto** | Sin acción |
| R-06 | ChromaDB sin disco persistente en Render free (se borra entre deploys) | Condiciones conocidas del free tier de Render | Sin probar | Alto para la persistencia (K11, T12) | Evaluar volumen persistente, Qdrant Cloud gratis o reindexar al arrancar |
| R-07 | RTX 4070 con 8 GB VRAM: un 7B q4 ajustado no cabe cómodo junto a los embeddings | Especificación verificada con `nvidia-smi`/WMI: 8 GB reales | Modelo 4B elegido (DEC-12): 67 tok/s | Bajo: resuelto con `qwen3.5:4b` | Mantener 4B; `qwen2.5:3b` como respaldo |
| R-08 | Pony API: último dato 2020, sin ToS explícita, datos CC BY-SA 3.0 | Documentación leída 2026-10-17 | Endpoint probado OK | Bajo-medio: obliga a atribución | Atribución obligatoria en README y en la app |

## 4. Plan alternativo de autenticación (si R-03 se confirma como inviable)

1. Intento 1: Keycloak en Docker localmente y en la nube (mismo `docker-compose`).
2. Si los free tiers no lo sostienen: **Keycloak solo local para la demostración presencial** + JWT propio verificado en la API desplegada, documentando la limitación con transparencia en el documento técnico.
3. Último recurso: JWT propio de extremo a extremo (permitido expresamente por el PDF §2.1: *"pueden emplear otra solución o implementarla por su cuenta"*).

Ninguna opción se aplicará sin comunicarlo y registrar el cambio aquí.

## 5. Pruebas realizadas y resultados

| Fecha | Prueba | Comando / método | Resultado |
|-------|--------|------------------|-----------|
| 2026-10-17 | Lectura del PDF | pypdf → `Temp\opencode\trabajo_agente.txt` | OK, 10 páginas, 14.736 caracteres |
| 2026-10-17 | Inventario del equipo | PowerShell `Win32_OperatingSystem`, `Get-Command` | Win11, i9-13980HX, 63,6 GB RAM, RTX 4070 4 GB, Node 24.13, Git 2.52, Docker 29.7 (daemon apagado), Python 3.14.2, Ollama ausente |
| 2026-10-17 | Pony API episodios | `curl /v1/episode/all?limit=10000` | HTTP 200, 243 registros, 1,07 s |
| 2026-10-17 | Pony API personajes | `curl /v1/character/all?limit=10000` | HTTP 200, 555 registros, 1,17 s |
| 2026-10-17 | Pony API canciones | `curl /v1/song/all?limit=10000` | HTTP 200, 192 registros |
| 2026-10-17 | CORS Pony API | cabecera con `Origin` | `Access-Control-Allow-Origin: *` |
| 2026-10-17 | Path con `%20` | `curl /v1/character/Twilight%20Sparkle` | **403 Forbidden** → usar IDs o guiones bajos |
| 2026-10-17 | SQLite de la API | HEAD `/ponydb.sqlite` | 200, 999.424 bytes |
| 2026-10-17 | Compatibilidad Python 3.14 | `pip install --dry-run` langgraph / chromadb / sentence-transformers | Resolución OK (falta ejecución real) |
| 2026-10-17 | Instalación de Ollama | `winget install Ollama.Ollama` | Instalado v0.40.5 |
| 2026-10-17 | Descarga de modelos | `ollama pull` | `qwen3.5:4b`, `qwen2.5:3b`, `qwen2.5:7b`, `nomic-embed-text` |
| 2026-10-17 | Generación local | `ollama run` | 67 tok/s en RTX 4070; primera carga ~45 s |
| 2026-10-17 | Embeddings + vectorial | script de ingesta | 808 documentos → 813 fragmentos en `backend\vectorstore` |
| 2026-10-17 | Importación Pony API | `python scripts\import_pony.py` | 10 fichas + 243 episodios + 555 personajes; 2ª ejecución omite 798 duplicados |
| 2026-10-17 | Bugs corregidos | iteración guiada por `scripts/debug_*.py` | reasoning de qwen3.5 vaciaba respuestas; `$contains` multi-token en Chroma; `content_hash` no se guardaba; JWT key corta; `EmailStr` rechazaba dominio `.test`; orden/deduplicación de resultados |
| 2026-10-17 | Smoke test (1.ª pasada) | `python scripts\smoke_test.py` | 9/10 — falló T07 (documento recién subido no consultable) |
| 2026-10-17 | Corrección T07 | deduplicación en cargas **por usuario** (`Document.user_id`) en `services/ingestion.py` | Causa: la deduplicación global descartaba el doc subido |
| 2026-10-17 | Reconstrucción limpia | borrar `data\ponyarchive.db` + `vectorstore\*` → `import_pony.py` | 808 documentos / 813 fragmentos (sin restos de pruebas) |
| 2026-10-17 | **Smoke test (final)** | `python scripts\smoke_test.py` | **11/11 OK**: health, register 201, 401 sin token, T01 factual con fuentes, T04 rechazo, T05 sin evidencia, historial B04, carga K07, T07 doc subido, T10 aislamiento de recuperación, T10b aislamiento de listado |
| 2026-10-17 | Frontend (Fase 6) | `npm create vite@latest frontend -- --template react-ts` + `npm run build` | Build sin errores (tsc + vite); `frontend/src` con chat, documentos, journal y login |
| 2026-10-17 | Flujo completo en navegador | Dev server en `http://localhost:5173` + navegador | Registro 201 y sesión, error 422 mostrado con claridad (dominio `.test`), login/logout (token borrado), chat con 6 fuentes y similitudes, rechazo con la frase literal, historial (9 conversaciones, apertura correcta), subida 201, borrado 204, Journal (temas y comparación) con fuentes |
| 2026-10-17 | **Bug 1: listado filtraba mal** | Observado en la UI: otro usuario veía `prueba_zecora.txt` como "Tuyo" | `GET /api/documents?scope=all` devolvía cargas ajenas → corregido en `routers/documents.py` con `or_(user_id == user.id, user_id IS NULL)`; nuevo caso **T10b** en el smoke test |
| 2026-10-17 | **Bug 2: pregunta sobre doc propio rechazada** | La UI y `debug_ui.py` devolvían `intent=fuera_de_dominio` → rechazo sin recuperar | `agents/graph.py`: el nodo de intención ahora recupera también en `fuera_de_dominio` y `evaluate_sufficiency` solo acepta si hay evidencia en documentos **subidos** por el usuario; T04 (fuera de dominio real) sigue rechazando → smoke 11/11 |
| 2026-10-17 | Tema oscuro | `frontend/src/index.css` reescrito con paleta noche; `npm run build` | Build OK; 4 capturas regeneradas en `docs/capturas/` (chat-fuentes, rechazo, documentos, journal) |
| 2026-10-17 | Contexto del curso (DEC-14) | Nota `contexto_curso.json` + regla de evidencia en `evaluate_sufficiency`; caso **T11** en el smoke | "¿A Duvan Gomez le pega la esposa?" → responde con la nota como fuente (sim 0.904); química/sushi siguen rechazados |
| 2026-10-17 | **Smoke test final ampliado** | `python scripts\smoke_test.py` | **12/12 OK** (añade T11: contexto del curso) |
| 2026-10-17 | Docker build | `docker compose build` | backend 4.24 GB (modelo e5 horneado), frontend 74 MB (multi-stage node→nginx) |
| 2026-10-17 | **E2E de compose** | `python scripts\e2e_compose.py` contra `localhost:8010` (nginx → backend) | **TODO CORRECTO**: health, register 201, import 243+555 → 814 fragmentos, chat factual 6 fuentes, rechazo literal, journal 6 fuentes, contexto del curso respondido |
| 2026-10-17 | Bug 3: semilla enmascarada por el volumen | `seed_contexto` devolvía `sin_notas` en el contenedor (el volumen `/app/data` ocultaba `/app/data/seed` de la imagen) | DEC-16: semilla en `/app/seed` + `PONYARCHIVE_SEED_DIR`; verificado con `creadas: 1` en el arranque |
| 2026-10-17 | Bug 4: búsqueda general condicionada | Cuando el clasificador proponía un `doc_type` (243 episodios llenaban el `top_k`), se saltaba la búsqueda complementaria y se perdía la evidencia de dominio (T11 fallaba de forma intermitente) | `retrieve()` hace la búsqueda general **siempre** que haya filtros; verificado en local (12/12) y en compose (TODO CORRECTO) |
| 2026-10-18 | Retirada de Friendship Journal (DEC-18) | Borrado de UI, endpoints y nodos del agente; `docker compose` y e2e ajustados | Backend 16 endpoints; frontend compila (`tsc -b && vite build`); e2e compose OK |
| 2026-10-18 | Bug spinner global (DEC-19.1) | El spinner "Consultando la base de conocimiento" se activaba en todas las conversaciones | `pendingKeys`/`viewKey`/`busyHere` en `ChatPage.tsx` + guard `viewRef` al colgar la respuesta; verificado en navegador |
| 2026-10-18 | Bug de catálogo (DEC-19.2) | "¿Cuántas temporadas/capítulos?" devolvía el conteo de tipos de documento | `fetch_documents(doc_type)` en `vectorstore.py` + `_season_breakdown()` en el grafo → desglose 9 temporadas / 221 capítulos + 22 especiales |
| 2026-10-18 | Alcance fijo del agente (DEC-19.3) | "¿Qué tipo de preguntas puedes contestar?" producía respuesta variable del LLM | Intent `meta` con `META_PATTERNS` (determinista, antes del LLM) → `agent_info` devuelve `AGENT_SCOPE` fijo (G4, 2010-2019) sin recuperación |
| 2026-10-18 | **Smoke test tras correcciones** | `python scripts\smoke_test.py` | **12/12 OK** (T11 Duvan afirmativo; rechazo literal intacto) |
| 2026-10-18 | Verificación de las 3 consultas reportadas | `Temp\opencode\test_reported.py` contra `localhost:8000` | Temporadas → desglose correcto; alcance → `AGENT_SCOPE` G4; factual Twilight → respuesta con fuentes |
| 2026-10-18 | Regeneración de entregables `docs/` | Edge headless `--print-to-pdf` | `documento-tecnico.pdf` 18 páginas OK; `presentacion.pdf` **9 páginas** (raíz del fallo: reveal.js inyecta `top:1px` en línea por lámina y `@media print` propio alteraba la tipografía; resuelto forzando `top:0` y aislando `reveal.css` a `media="screen"`) |

## 6. Próximo paso concreto

**Objetivo:** cierre de la entrega del 2026-10-18.
**Pendientes:** (1) commits granulares + push a `github.com/navyri/PonyArchive` (hay ~20 archivos sin commitear: Journal retirado, correcciones del agente, `render.yaml`, `docs/`); (2) despliegue nube M8 en cuanto María facilite `OPENAI_API_KEY`, `QDRANT_URL` y `QDRANT_API_KEY` (Render/Vercel/Qdrant Cloud) y re-ejecución del smoke contra la nube; (3) guion de la demo de 7–10 min (§1.4: login, chat con fuentes, rechazo, historial, grafo, evidencia de despliegue).
**Criterio de aceptación:** `git log` muestra los commits con sus fechas reales y el repo remoto accesible; smoke 12/12 contra el backend desplegado.
**Evidencia que debe compartir María:** salida de `git log --oneline`, URL del repo y URL del backend desplegado.
