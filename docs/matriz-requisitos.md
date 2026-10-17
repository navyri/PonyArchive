# PonyArchive — Matriz requisito → componente → prueba → evidencia

Fuente: "trabajo agente.pdf" (10 páginas, leído el 2026-10-17). Cuando PDF y prompt difieren, **gana el PDF**.

Leyenda de tipo: **[O]** requisito obligatorio del profesor · **[D]** decisión técnica aprobada · **[P]** propuesta pendiente · **[M]** mejora opcional.

## 1. Requisitos mínimos para aprobar (§6.1) — sin ellos, nota 0

| ID PDF | Requisito | Componente | Prueba | Evidencia esperada | Tipo | Estado |
|--------|-----------|------------|--------|--------------------|------|--------|
| M1 | Backend y frontend funcionales | `backend/`, `frontend/` | Flujo completo en local: pregunta → respuesta | Captura + demo en vivo | [O] | [ ] |
| M2 | Autenticación implementada | Módulo de auth | Registro, login, logout; 401 sin token | Demo §5.3 | [O] | [ ] |
| M3 | Agente con LangChain y LangGraph | `backend/agents/` | Ver código del grafo + ejecución | Repositorio + demo | [O] | [ ] |
| M4 | Modelo local en funcionamiento | Ollama en portátil | `ollama list` + respuesta generada | Registro en doc técnico §8 | [O] | [~] instalando |
| M5 | Base vectorial + carga de documentos operativa | ChromaDB + pipeline | Subir archivo → indexar → consultar | Demo en vivo | [O] | [ ] |
| M6 | Respuestas fundamentadas en el contexto recuperado | Nodo de generación | Preguntas T01/T02 con fuente verificable | Salida con fuentes | [O] | [ ] |
| M7 | Rechazo explícito sin información suficiente | Nodo de rechazo | Preguntas T04/T05 | Mensaje literal del §3.1 | [O] | [ ] |
| M8 | Despliegue en la nube + repositorio documentado | Render/Vercel + GitHub | URL pública accesible | URLs en doc técnico §12 | [O] | [ ] |

## 2. Requisitos funcionales (§2)

| ID PDF | Requisito | Componente | Prueba | Evidencia | Tipo | Estado |
|--------|-----------|------------|--------|-----------|------|--------|
| F1 | Registro o inicio de sesión | Auth | Crear usuario, entrar | Captura | [O] | [ ] |
| F2 | Frontend accesible solo autenticado | Rutas protegidas frontend | Abrir app sin sesión → redirige a login | Captura | [O] | [ ] |
| F3 | API solo con autorización | Middleware backend | `curl` sin token → 401 | Log/respuesta HTTP | [O] | [ ] |
| F4 | Sesión activa + cierre de sesión | Auth | Login persistente y logout | Captura | [O] | [ ] |
| F5 | Enviar preguntas al agente y recibir respuestas | Endpoint chat | Flujo de chat | Respuesta JSON | [O] | [ ] |
| F6 | Subir archivos | Endpoint upload | Subir PDF/TXT | Doc indexado | [O] | [ ] |
| F7 | Procesar docs: extraer → trocear → embeddings → vectorial | Pipeline | Subir y verificar chunks en la BD | Registros en Chroma | [O] | [ ] |
| F8 | Consultar historial por usuario | Endpoint historial | 2 usuarios → historiales aislados | Dos respuestas distintas | [O] | [ ] |
| F9 | Listar documentos (y eliminar "si aplica") | Endpoint docs | Listar tras subir | JSON con lista | [O] | [ ] |
| F10 | Frontend: chatbot, subir, listar, errores, logout | UI | Recorrido manual | Capturas | [O] | [ ] |

## 3. Requisitos técnicos (§3)

| ID PDF | Requisito | Componente | Prueba | Evidencia | Tipo | Estado |
|--------|-----------|------------|--------|-----------|------|--------|
| T1 | Flujo de 7 pasos del agente con grafo | `agents/graph.py` | Inspección de nodos y aristas | Código + diagrama | [O] | [ ] |
| T2 | Mensaje literal de rechazo "No tengo suficiente información…" | Nodo de rechazo | Pregunta fuera de dominio | Captura | [O] | [ ] |
| T3 | Modelo local (Ollama o Hugging Face), no solo comercial | Servicio LLM | Configuración apunta a localhost | Doc técnico §8 | [O] | [~] |
| T4 | Base vectorial almacena fragmentos + relación con doc original | ChromaDB | Ver metadatos de chunks | Consulta a la BD | [O] | [ ] |
| T5 | **≥2 estrategias anti-alucinación** (§3.4) | Nodo suficiencia + umbral + prompt + fuentes | Preguntas T04/T05 | Doc técnico §10 + demo | [O] | [ ] |
| T6 | Backend y frontend con URL pública | Render / Vercel | Abrir en navegador anónimo | URL pública | [O] | [ ] |

## 4. Restricciones (§4)

| ID PDF | Restricción | Verificación | Tipo | Estado |
|--------|-------------|--------------|------|--------|
| R-1 | Flujo del agente con código (LangChain/LangGraph), **prohibido** n8n/Zapier/Make/Flowise/Botpress visual | Revisión del código fuente | [O] | [x] cumplido por diseño: todo será código Python |
| R-2 | No dependencia exclusiva de modelos comerciales | Configuración del LLM | [O] | [D] Ollama local aprobado |

## 5. Entregables (§5)

| ID | Entregable | Especificación | Tipo | Estado |
|----|-----------|----------------|------|--------|
| E-a | Repositorio GitHub público | Código + README + `.env.example` + capturas + diagrama | [O] | [ ] |
| E-b | Documento técnico PDF | 14 apartados (§5.2) | [O] | [ ] |
| E-c | Demostración | 7–10 min, **presencial** | [O] | [ ] |
| E-d | Diapositivas | 8–12 láminas con la secuencia §5.4 | [O] | [ ] |

## 6. Diferencias PDF vs. prompt del proyecto

| # | Diferencia | Resolución (PDF manda) |
|---|-----------|------------------------|
| 1 | El PDF no menciona Friendship Journal, comparación de episodios ni 10–15 fichas | Son **[P] propuestas del proyecto**, no requisitos. No se presentan como aprobadas |
| 2 | El PDF sugiere formatos multimedia (JPG, MP4, MP3) | Es "sugerido", no obligatorio. El alcance actual los deja fuera: **sin conflicto** |
| 3 | A11 (inyección de instrucciones en documentos) no está en el PDF | **[M]** mejora opcional, se mantiene si hay tiempo |
| 4 | §5.3: la sustentación es **presencial** | Condiciona que el modelo corra en el portátil durante la demo |
| 5 | Keycloak es "recomendado", se permite implementación propia | El equipo eligió Keycloak → riesgo R-03 registrado |

## 7. Tensión documentada: protección de endpoints (§2.1)

El PDF dice: *"ningún endpoint puede quedar expuesto al consumo sin autenticación"*. Propuesta de tratamiento (**[P], pendiente de aprobación/consulta al profesor**):

| Grupo | Rutas | Tratamiento |
|-------|-------|-------------|
| Autenticación | registro, login, refresh, logout | Sin token previo **por definición**: son el mecanismo de obtención de token. Se protegen con rate limiting, validación de entrada, HTTPS y hashing de contraseñas |
| Infraestructura | `/health`, preflight `OPTIONS` de CORS, comprobación de versión | Stateless, sin datos de negocio, respuesta mínima y sin efectos secundarios |
| **Negocio** (todos) | chat, historial, documentos, importación, consultas temáticas | Bearer token obligatorio + verificación de pertenencia por usuario. Prueba automatizada: sin token → **401**, con token de otro usuario → **403** |

Riesgo asociado R-04: la redacción del PDF es literal y podría interpretarse en sentido estricto. Se documentará abiertamente en el apartado 11 del documento técnico y se consultará al profesor si hay margen.
