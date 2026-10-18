# Guion de la demostración en vivo — PonyArchive (7–10 min)

Sustentación §5.3: la demo debe cubrir los 7 puntos marcados con ✔. Duración objetivo: ~9 min.
Todo se ejecuta contra `http://localhost:5174` (frontend) y `http://127.0.0.1:8000` (backend, Ollama local).

## Preparación previa (antes de que entre el público)

- Backend arrancado (`uvicorn app.main:app`) y verificado: `GET /health` → `ok`; en la UI debe verse **API OK · 2863 frag.**
- Frontend en `http://localhost:5174`.
- Ollama corriendo con `qwen3.5:4b` precargado (evita los ~45 s de la primera carga).
- Sesión cerrada (pantalla de login). Historial de chat limpio.
- Diapositivas (`docs/presentacion.pdf`) a mano por si cae la red o el proyector.
- Respaldo: capturas en `docs/capturas/` por si algo falla en vivo.

---

## 1 · Tema y arquitectura (~1,5 min) ✔ "Presentación del tema y de la arquitectura"

- Tema: biblioteca inteligente de **My Little Pony: Friendship Is Magic** (2010–2019, G4). Corpus: 1.015 documentos / 3.100 fragmentos (243 episodios, 555 personajes con descripción de Fandom CC BY-SA, 192 canciones, 10 fichas narrativas propias y 1 nota de contexto del curso).
- Diapositiva de arquitectura: React + Vite + TS (frontend) → FastAPI (17 endpoints) → **grafo LangGraph** (valida intención → recupera → evalúa suficiencia → genera o rechaza → persiste) → ChromaDB + Ollama `qwen3.5:4b` + embeddings `multilingual-e5-small`.
- Frase clave: *"El agente no responde de memoria: solo con lo que hay indexado, y si no hay evidencia, lo dice."*

## 2 · Login y frontend (~1 min) ✔ "Inicio de sesión del usuario y ejecución del frontend"

- Abrir `localhost:5174` → pantalla de login (tema oscuro "terminal mágica").
- Registrar un usuario nuevo **o** entrar con el de demo → 201/login OK, aparece el chat con el historial.
- Mencionar: la API rechaza con 401 cualquier llamada sin token (protección real, no solo cosmética).

## 3 · Preguntas bien respondidas (~2 min) ✔ "Interacción con el agente, con preguntas correctamente respondidas"

Elegir dos de estas (las tres están verificadas):

- **"¿Quién es Rarity?"** → respuesta con interpretación, sección "No está documentado" y **fuentes citadas** [1]–[4] con tipo y origen.
- **"¿De qué trata el episodio Bridle Gossip?"** → sinopsis fundamentada con fuentes de episodio.
- **"¿Cuántas temporadas tiene MLP y cuántos capítulos tiene cada temporada?"** → desglose por temporada (9 temporadas, 221 capítulos numerados + 22 especiales), no un conteo genérico.
- Señalar en pantalla las **fuentes citadas** y las similitudes: esto es la base de la anti-alucinación.

## 4 · Rechazo por falta de información (~1,5 min) ✔ "Preguntas que el agente rechaza por falta de información"

- Preguntar algo fuera del corpus, p. ej. **"¿Cuál es el código del pastel de manzana y dónde se cultiva?"** o una de química/sushi.
- El agente devuelve la frase literal: *"No tengo suficiente información en mi base de conocimiento para responder esa pregunta."* (con la ruta `reject` del grafo).
- Preguntar **"¿Qué tipo de preguntas puedes contestar?"** → respuesta fija y determinista del alcance (G4, 2010–2019), sin que el LLM improvise.

## 5 · Carga de documento + pregunta que depende de él (~2 min) ✔ "Carga de un documento nuevo y una pregunta que dependa de ese documento"

- Pestaña **Documentos** → "Elegir archivo" → subir un `.txt`/`.md` pequeño y nuevo (p. ej. una nota inventada con un dato inventado: "El Pastel de Manzana de Rarity se llama *Sweetie Belle Cheesecake* y se hornea en Canterlot").
- Volver al chat y preguntar por ese dato nuevo → el agente responde citando **el documento recién subido** (T07 del smoke test).
- Contraste rápido: sin ese documento, la misma pregunta se rechazaba. Esto demuestra la recuperación filtrada por usuario.

## 6 · Código y grafo LangGraph (~1,5 min) ✔ "Revisión rápida del código y explicación del grafo construido con LangGraph"

- Abrir `backend/app/agents/graph.py` y señalar:
  - `META_PATTERNS` + intent `meta` (detección determinista antes del LLM).
  - `g.add_node(...)` / `g.add_conditional_edges(...)` en texto plano: **grafo en código, sin constructores visuales** (requisito explícito).
  - `evaluate_sufficiency` (umbral de similitud) y la ruta condicional `sufficient ? "generate" : "reject"`.
  - Las 7 estrategias anti-alucinación repartidas en los nodos: umbral, suficiencia, prompt restringido con citas, rechazo literal, fuentes, validación de entidades y catálogo por SQL sin LLM.

## 7 · Evidencia de despliegue en nube (~1 min) ✔ "Evidencia del despliegue en la nube"

- Mostrar `render.yaml` (backend) + `docs/despliegue-nube.md` (flags dual `EMBEDDINGS_PROVIDER|LLM_PROVIDER|VECTOR_PROVIDER`).
- Si ya hay credenciales: abrir la URL pública de Render + la de Vercel y hacer una pregunta en vivo contra la nube.
- Si aún no hay credenciales: mostrar los recursos configurados y el smoke local 12/12 como evidencia del pipeline reproducible; explicar que los free tiers (Render/Vercel/Qdrant Cloud) mantienen el coste en 0 USD.

## Cierre (30 s)

- Requisitos mínimos cumplidos: backend + frontend, auth, agente LangChain/LangGraph, modelo local, base vectorial con carga de archivos, respuestas fundamentadas, rechazo literal, despliegue 0 USD y repo documentado.
- Conclusiones de la diapositiva 9: un modelo de 4B basta cuando el RAG hace el trabajo pesado.
- Preguntas del público.

---

## Contingencias

- **Ollama lento / sin GPU**: la primera carga tarda ~45 s. Tener el modelo ya cargado; si falla, usar la reserva `qwen2.5:3b`.
- **Pregunta en vivo falla**: reintentar una vez; si insiste, usar la respuesta ya guardada en el historial de la demo y explicar la ruta del grafo que tomó.
- **Proyector / red caídos**: presentar con `docs/presentacion.pdf` y las capturas de `docs/capturas/`.
- **Nube sin credenciales**: no prometer URL que no existe; mostrar `render.yaml` + flags y el smoke local.
