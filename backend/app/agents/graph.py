"""Grafo de LangGraph: validación de intención, recuperación, evaluación de
suficiencia, generación o rechazo, validación de respuesta e historial."""
from __future__ import annotations

import json
import re
from typing import Callable

from langgraph.graph import END, START, StateGraph
from sqlalchemy import func

from app.agents.state import AgentState
from app.config import get_settings
from app.database import SessionLocal
from app.models import Conversation, Document, Message
from app.services.embeddings import embed_query
from app.services.llm import get_llm
from app.services.themes import theme_from_query
from app.services.vectorstore import fetch_documents, search

REFUSAL_MESSAGE = (
    "No tengo suficiente información en mi base de conocimiento para responder esa pregunta."
)
SUGGESTION = "Puedes subir documentos relacionados con ese tema y lo tendré en cuenta en la siguiente consulta."

# Bonus de similitud para los fragmentos de los documentos que subió el usuario
BONUS_PROPIO = 0.05

# Preguntas sobre el propio agente: respuesta fija, sin LLM ni recuperación
META_PATTERNS = (
    r"qu[eé] (tipo de )?preguntas",
    r"qu[eé] puedes (contestar|responder|hacer|saber)",
    r"para qu[eé] sirves",
    r"qui[eé]n eres",
    r"c[oó]mo funcionas",
    r"cu[aá]l es tu (funci[oó]n|capacidad|prop[oó]sito|alcance)",
    r"en qu[eé] me puedes (ayudar|servir)",
)

# Recuento de temporadas o canciones: preguntas estructuradas, resueltas con E7
SEASON_COUNT_RE = re.compile(r"cu[aá]nt(as|os)[^.?!]{0,60}temporada", re.IGNORECASE)
SONG_COUNT_RE = re.compile(r"cu[aá]nt(as|os)[^.?!]{0,40}cancion", re.IGNORECASE)

AGENT_SCOPE = """Soy PonyArchive, el agente de esta biblioteca sobre My Little Pony: Friendship Is Magic
(la generación G4, 2010-2019). Uso únicamente la documentación indexada, así que puedo
responder sobre:

- Episodios de la serie: trama, personajes que aparecen, canciones y cuántos episodios
  documenta la biblioteca por temporada.
- Personajes de G4: quiénes son, su rol y sus relaciones con otros personajes.
- Fichas narrativas de la biblioteca, con temas como la amistad, la confianza o la
  generosidad.
- Notas de contexto del curso (p. ej. información sobre el profesor Duvan Gomez) y los
  documentos que subas a tu biblioteca.

También puedo comparar personajes o episodios entre sí, y decir cuántos episodios,
personajes u otros documentos hay indexados. Todo lo que respondo sale de esos
documentos: si la pregunta está fuera de ese alcance, lo digo explícitamente en lugar
de rellenar con conocimiento general."""

INTENT_PROMPT = """Eres el clasificador de intenciones de PonyArchive, una biblioteca sobre
My Little Pony: Friendship Is Magic. La biblioteca contiene episodios, personajes, canciones,
fichas narrativas propias, documentos subidos por el usuario y notas de contexto del curso
(p. ej. la nota sobre Duvan Gomez, profesor de la EIA).
Clasifica la pregunta del usuario y extráe filtros.

Responde SOLO con un objeto JSON exactamente con esta forma:
{{"intent": "factual|tematica|comparacion|catalogo|meta|fuera_de_dominio|ambigua",
  "tema": "una etiqueta entre confianza, celos, reconciliación, trabajo en equipo, amistad,
           honestidad, responsabilidad, liderazgo, valentía, generosidad, paciencia o null",
  "titulo": "nombre propio citado (episodio, personaje o canción) que la pregunta quiera acotar, o null",
  "tipo_documento": "episodio|personaje|cancion|ficha_narrativa|upload|null",
  "elementos": ["hasta dos nombres propios si la pregunta COMPARA elementos, o lista vacía"],
  "aclaracion": "si la pregunta es ambigua, una pregunta corta para aclararla; si no, null"}}

Reglas:
- "catalogo" solo si pide contar o enumerar registros (ej. ¿cuántos episodios hay?, ¿cuántas
  temporadas se documentan?, ¿cuántos capítulos tiene la temporada 3?).
- "meta" si pregunta por el propio agente: qué puede o no responder, qué tipo de preguntas
  contesta, quién es o cómo funciona.
- "fuera_de_dominio" si no guarda relación con la serie, sus personajes, sus temas NI con
  los documentos de la biblioteca (incluidos los archivos que el usuario haya subido y las
  notas de contexto del curso): una pregunta sobre un documento de la biblioteca NO es
  fuera de dominio, aunque trate otro asunto.
- Duvan Gomez (o "Duvan"), profesor de la EIA, es contexto del curso documentado en la
  biblioteca: esas preguntas son "factual", no "fuera_de_dominio".
- "ambigua" si podría referirse a varias cosas sin poder resolverse.
- No inventes nombres: si no estás seguro, usa null."""

GENERATE_PROMPT = """Eres PonyArchive, un asistente que responde EXCLUSIVAMENTE a partir del contexto
documental recuperado de la biblioteca (My Little Pony: Friendship Is Magic, documentos subidos
por el usuario y notas de contexto del curso).

REGLAS INQUEBRANTABLES:
1. Usa SOLO la información de los fragmentos [Documento N]. NO uses tu conocimiento previo.
2. Si el contexto no contiene la respuesta, responde EXACTAMENTE:
   "{refusal}" y termina con: {suggestion}
3. Distingue siempre entre "Dato documentado:" (información literal de la fuente) e
   "Interpretación del documento:" (inferencia razonable a partir de ella). Si algo no
   aparece, di "No está documentado en la biblioteca" en lugar de rellenarlo.
4. No inventes nombres, episodios, fechas, moralejas ni relaciones entre personajes.
5. Cita las fuentes al final como [1], [2]... con título y tipo de documento.
6. Responde en español, claro y breve, pero copia los nombres propios tal como
   aparecen en los fragmentos (p. ej. "Princess Celestia", no "Princesa Celestia"):
   así quien lea puede rastrearlos en la fuente.
{extra_rule}

CONTEXTO DOCUMENTAL:
{context}

PREGUNTA DEL USUARIO:
{question}"""


def _parse_json(text: str) -> dict:
    """Extrae el primer objeto JSON de la respuesta del modelo."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}


def _context_blocks(retrieved: list[dict]) -> str:
    blocks = []
    for i, item in enumerate(retrieved, 1):
        meta = item.get("metadata", {})
        blocks.append(
            f"[Documento {i}] {meta.get('title', 'Sin título')} "
            f"({meta.get('doc_type', 'documento')}, {meta.get('source', 'biblioteca')})\n"
            f"{item['text']}"
        )
    return "\n\n".join(blocks)


def _source_list(retrieved: list[dict]) -> list[dict]:
    out = []
    for item in retrieved:
        meta = item.get("metadata", {})
        out.append(
            {
                "doc_id": meta.get("doc_id"),
                "title": meta.get("title", "Sin título"),
                "doc_type": meta.get("doc_type", ""),
                "source": meta.get("source", ""),
                "source_url": meta.get("source_url", ""),
                "fragment": item["text"][:400],
                "score": round(float(item.get("score", 0.0)), 4),
            }
        )
    return out


def _norm_text(s: str) -> str:
    """Minúsculas sin acentos ni puntuación."""
    table = str.maketrans("áéíóúüñ?¡¿.,:;!()", "aeiouun          ")
    return " ".join(s.lower().translate(table).split())


def _fuzzy_contains(haystack: str, needle: str) -> bool:
    """Coincidencia tolerante a acentos, mayúsculas y puntuación."""
    return _norm_text(needle) in _norm_text(haystack)


def _documented_title_in(question: str) -> str | None:
    """Título de la biblioteca compartida citado literalmente en la pregunta."""
    norm_q = _norm_text(question)
    db = SessionLocal()
    try:
        titles = [
            t for (t,) in db.query(Document.title)
            .filter(Document.user_id.is_(None), Document.status == "indexado")
            .all()
        ]
    finally:
        db.close()
    return next(
        (t for t in titles if len(_norm_text(t)) >= 10 and _norm_text(t) in norm_q),
        None,
    )


def validate_intent(state: AgentState) -> dict:
    """Nodo 2 del flujo del enunciado: validar la intención de la pregunta."""
    question = state["question"]
    defaults = {
        "intent": "factual",
        "theme": theme_from_query(question),
        "titulo": None,
        "tipo_documento": None,
        "elementos": [],
        "aclaracion": None,
    }

    # Detección determinista de preguntas sobre el propio agente (E7): evita que el
    # clasificador pequeño las mande a recuperación y el LLM rellene con fragmentos sueltos.
    if any(re.search(p, question, re.IGNORECASE) for p in META_PATTERNS):
        return {
            "intent": "meta",
            "theme": None,
            "title_filter": None,
            "doc_type_filter": None,
            "compare_items": [],
            "clarification": None,
        }

    try:
        raw = get_llm().invoke(INTENT_PROMPT + "\n\nPREGUNTA: " + question).content
        parsed = _parse_json(raw)
    except Exception:
        parsed = {}
    data = {**defaults, **{k: parsed.get(k) for k in defaults if parsed.get(k) is not None}}

    intent = data["intent"] if data["intent"] in {
        "factual", "tematica", "comparacion", "catalogo", "meta", "fuera_de_dominio", "ambigua"
    } else "factual"

    # Los recuentos de temporadas o canciones se resuelven con SQL/E7 aunque el
    # clasificador los haya tratado como pregunta factual (bug del 2026-10-18).
    if SEASON_COUNT_RE.search(question) or SONG_COUNT_RE.search(question):
        intent = "catalogo"

    # Un título documentado citado en la pregunta anula un "fuera_de_dominio"
    # erróneo del clasificador (bug del 2026-10-18) y acota la recuperación.
    titulo = data["titulo"]
    if intent == "fuera_de_dominio":
        citado = _documented_title_in(question)
        if citado:
            intent, titulo = "factual", citado

    return {
        "intent": intent,
        "theme": data["theme"],
        "title_filter": titulo,
        "doc_type_filter": data["tipo_documento"],
        "compare_items": data["elementos"] or [],
        "clarification": data["aclaracion"],
    }


def retrieve(state: AgentState) -> dict:
    """Nodo 3: buscar información relevante en la base vectorial, con filtros."""
    question = state["question"]
    settings = get_settings()
    notes: list[str] = []
    results: list[dict] = []
    propios: list[dict] = []

    def _search(q: str, **kwargs) -> list[dict]:
        # Por defecto solo se ven los documentos compartidos y los propios del
        # usuario: los subidos por otros usuarios quedan fuera (aislamiento, T10).
        kwargs.setdefault("visible_to", state.get("user_id"))
        try:
            return search(embed_query(q), k=settings.top_k, **kwargs)
        except Exception as exc:
            notes.append(f"Error de recuperación: {exc}")
            return []

    # Prioridad de los documentos que el propio usuario subió: sin este bonus,
    # la biblioteca compartida (cientos de fichas) ahogaba el documento recién
    # cargado (bug reproducido el 2026-10-17 en la prueba T07).
    user_id = state.get("user_id")
    if user_id:
        propios = _search(question, user_id=user_id)
        for r in propios:
            r["score"] = min(1.0, r["score"] + BONUS_PROPIO)
            r["metadata"]["es_propio"] = True
        if propios:
            notes.append(
                f"{len(propios)} fragmento(s) de tus propios documentos "
                f"(bonus de similitud +{BONUS_PROPIO})."
            )

    compare_items = state.get("compare_items") or []
    if state.get("intent") == "comparacion" and compare_items:
        # Búsqueda acotada por elemento comparado: cada uno con su propio contexto
        for item in compare_items:
            found = _search(question, title_contains=item)
            if len(found) < 2:
                # El nombre puede aparecer dentro del texto y no en el título
                notes.append(f"Sin coincidencias por título para '{item}'; búsqueda ampliada.")
                found = _search(item)
            found.sort(key=lambda r: r["score"], reverse=True)
            for f in found[:3]:
                f["metadata"]["compare_item"] = item
            results.extend(found[:3])   # se garantiza contexto propio de cada elemento
    else:
        con_filtros = _search(
            question,
            doc_type=state.get("doc_type_filter"),
            title_contains=state.get("title_filter"),
        )
        results.extend(con_filtros)
        # Los filtros que extrae el modelo pueden ser demasiado estrechos (p. ej.
        # tipo "personaje" excluye un documento subido por el usuario, o una nota
        # de contexto del curso). La búsqueda general complementaria se hace SIEMPRE
        # que haya filtros: si se condicionaba a "menos de top_k resultados", una
        # búsqueda filtrada que llenara las plazas (243 episodios) la saltaba y se
        # perdía la evidencia de dominio (bug reproducido el 2026-10-17 con T11).
        if state.get("title_filter") or state.get("doc_type_filter"):
            notes.append(
                "Filtros propuestos por la clasificación de intención; "
                "búsqueda general complementaria para no perder documentos."
            )
            results.extend(_search(question))
        # Consulta temática: refuerzo filtrando por la etiqueta del tema
        # Refuerzo temático: trabaja sobre etiquetas del índice, no sobre suposiciones
        if state.get("theme"):
            themed = _search(question, theme=state["theme"])
            seen = {r["text"] for r in results}
            results.extend([r for r in themed if r["text"] not in seen])
            notes.append(
                f"Refuerzo temático con la etiqueta '{state['theme']}' "
                f"({len(themed)} fragmento(s) coincidentes)."
            )

    # Orden global por similitud y eliminación de duplicados entre búsquedas
    results = propios + results
    results.sort(key=lambda r: r["score"], reverse=True)
    seen_texts: set[str] = set()
    unique: list[dict] = []
    for r in results:
        if r["text"] not in seen_texts:
            seen_texts.add(r["text"])
            unique.append(r)
    results = unique

    # Auditoría: qué descarta el umbral (se conserva para explicar el rechazo)
    accepted = [r for r in results if r["score"] >= settings.similarity_threshold]
    rejected = [r for r in results if r["score"] < settings.similarity_threshold]
    if rejected:
        notes.append(
            f"{len(rejected)} fragmento(s) descartados por similitud "
            f"< {settings.similarity_threshold} (máximo {max(r['score'] for r in rejected):.3f})."
        )
    top = accepted[: settings.top_k]
    if top:
        notes.append(f"Similitud máxima: {max(r['score'] for r in top):.3f}.")

    return {"retrieved": top, "retrieval_notes": notes}


def evaluate_sufficiency(state: AgentState) -> dict:
    """Nodos 4 y 6 (estrategias E1 y E2): decide si el contexto permite responder."""
    settings = get_settings()
    threshold = settings.similarity_threshold
    retrieved = state.get("retrieved", [])
    intent = state.get("intent", "factual")

    if intent == "catalogo":
        # Los conteos se resuelven con SQL, nunca por similitud (E7)
        return {"sufficient": True, "refusal_reason": None}

    if intent == "fuera_de_dominio":
        # Solo se responde con documentos subidos por el usuario o notas de contexto
        # del curso; el resto de la biblioteca es de la serie.
        # retrieved ya viene filtrado por el umbral (E1).
        evidencia = [
            r
            for r in retrieved
            if r.get("metadata", {}).get("doc_type") in ("upload", "nota_curso")
        ]
        if not evidencia:
            return {
                "sufficient": False,
                "refusal_reason": "La pregunta no guarda relación con el dominio documentado.",
            }

    if intent == "comparacion":
        compare_items = state.get("compare_items") or []
        covered = {
            item for item in compare_items
            if any(_fuzzy_contains(r["metadata"].get("title", ""), item) for r in retrieved)
        }
        if len(covered) < min(2, len(compare_items) or 2):
            return {
                "sufficient": False,
                "refusal_reason": (
                    "La comparación requiere documentación de ambos elementos; solo hay "
                    f"contexto de: {', '.join(sorted(covered)) or 'ninguno'}."
                ),
            }

    if not retrieved:
        return {
            "sufficient": False,
            "refusal_reason": "Ningún fragmento de la biblioteca superó el umbral de similitud.",
        }

    if max(r["score"] for r in retrieved) < threshold:
        return {
            "sufficient": False,
            "refusal_reason": f"La similitud máxima ({max(r['score'] for r in retrieved):.3f}) es inferior al umbral ({threshold}).",
        }

    return {"sufficient": True, "refusal_reason": None}


def _season_breakdown() -> tuple[dict[int, int], int]:
    """Episodios por temporada (regex «Temporada N, episodio») y especiales sin número.

    Los fragmentos se agrupan por documento para que cada episodio se cuente una vez.
    """
    texts_por_doc: dict[int, list[str]] = {}
    for item in fetch_documents("episodio"):
        doc_id = item["metadata"].get("doc_id")
        if doc_id is not None:
            texts_por_doc.setdefault(doc_id, []).append(item["text"])

    counts: dict[int, int] = {}
    especiales = 0
    for texts in texts_por_doc.values():
        temporada = None
        for text in texts:
            match = re.search(r"Temporada (\d+), episodio", text)
            if match:
                temporada = int(match.group(1))
                break
        if temporada is None:
            especiales += 1
        else:
            counts[temporada] = counts.get(temporada, 0) + 1
    return counts, especiales


def catalog_query(state: AgentState) -> dict:
    """Estrategia E7: consultas estructuradas para contar o enumerar el catálogo."""
    db = SessionLocal()
    try:
        rows = (
            db.query(Document.doc_type, func.count(Document.id))
            .filter(Document.status == "indexado")
            .group_by(Document.doc_type)
            .all()
        )
    finally:
        db.close()

    if not rows:
        answer = REFUSAL_MESSAGE + " " + SUGGESTION
        return {"answer": answer, "sources": [], "refused": True}

    total = sum(c for _, c in rows)
    lines = ["Dato documentado (consulta directa al catálogo, no por similitud):"]
    for doc_type, count in sorted(rows, key=lambda r: -r[1]):
        lines.append(f"- {count} documento(s) de tipo '{doc_type}'.")
    lines.append(f"Total indexado: {total} documentos.")

    # Desglose de episodios por temporada: se extrae del texto documental, sin LLM
    if any(dt == "episodio" for dt, _ in rows):
        por_temporada, especiales = _season_breakdown()
        if por_temporada:
            detalle = ", ".join(
                f"Temporada {t}: {c}" for t, c in sorted(por_temporada.items())
            )
            line = (
                f"My Little Pony: Friendship Is Magic está documentada en "
                f"{len(por_temporada)} temporadas con {sum(por_temporada.values())} "
                f"capítulos numerados — {detalle}."
            )
            if especiales:
                line += (
                    f" Además hay {especiales} especiales (películas y Equestria Girls) "
                    f"sin número de temporada."
                )
            lines.append(line)
    return {"answer": "\n".join(lines), "sources": [], "refused": False}


def agent_info(state: AgentState) -> dict:
    """Respuesta fija sobre el alcance del agente (sin LLM ni recuperación)."""
    return {"answer": AGENT_SCOPE, "sources": [], "refused": False}


def generate(state: AgentState) -> dict:
    """Nodo 5: responder con base en la información encontrada (estrategia E3)."""
    retrieved = state.get("retrieved", [])
    extra_rule = ""
    if state.get("retry_count", 0) > 0:
        extra_rule = (
            "7. CORRECCIÓN: tu respuesta anterior usaba entidades que no aparecen en el contexto. "
            "Reformula usando EXCLUSIVAMENTE los términos presentes en los fragmentos."
        )
    prompt = GENERATE_PROMPT.format(
        refusal=REFUSAL_MESSAGE,
        suggestion=SUGGESTION,
        extra_rule=extra_rule,
        context=_context_blocks(retrieved),
        question=state["question"],
    )
    try:
        answer = get_llm().invoke(prompt).content.strip()
    except Exception as exc:
        return {
            "answer": f"El modelo local no está disponible en este momento ({exc}).",
            "refused": True,
        }

    refused = answer.startswith(REFUSAL_MESSAGE)
    return {"answer": answer, "sources": [] if refused else _source_list(retrieved), "refused": refused}


def _entity_supported(entity: str, context: str) -> bool:
    """La entidad consta en el contexto, tolerando la traducción del nombre común."""
    norm_e = _norm_text(entity)
    if norm_e in context:
        return True
    # La parte distintiva del nombre (última palabra) basta si aparece:
    # "Princesa Celestia" -> "celestia" sí está en el contexto en inglés.
    words = norm_e.split()
    return len(words) > 1 and len(words[-1]) >= 4 and words[-1] in context


def validate_answer(state: AgentState) -> dict:
    """Estrategia E6: verifica que las entidades de la respuesta existan en el contexto."""
    if state.get("refused"):
        return {"grounded": True}

    answer = state.get("answer", "")
    context = _norm_text(" ".join(r["text"] for r in state.get("retrieved", [])))

    # Entidades: secuencias de nombres propios de la respuesta
    entities = re.findall(r"[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)+", answer)
    # Se ignoran las citas [1], [2] y frases fijas del propio sistema
    entities = [e for e in entities if e not in ("Dato documentado", "Interpretación del documento")]
    if not entities:
        return {"grounded": True}

    unsupported = [e for e in entities if not _entity_supported(e, context)]
    ratio = len(unsupported) / len(entities)
    grounded = ratio <= 0.5 or len(unsupported) == 0
    if not grounded:
        return {
            "grounded": False,
            "retry_count": state.get("retry_count", 0) + 1,
        }
    return {"grounded": True}


def reject(state: AgentState) -> dict:
    """Nodo de rechazo (estrategia E4): mensaje explícito, del enunciado."""
    reason = state.get("refusal_reason") or "Contexto insuficiente."
    clarification = state.get("clarification")
    answer = REFUSAL_MESSAGE
    if clarification:
        answer += f" Para ayudarte mejor, ¿podrías aclarar qué quieres decir con: {clarification}?"
    answer += f" {SUGGESTION}"
    return {"answer": answer, "sources": [], "refused": True, "refusal_reason": reason}


def persist(state: AgentState) -> dict:
    """Nodo 7: guardar la interacción en el historial del usuario."""
    db = SessionLocal()
    try:
        conversation_id = state.get("conversation_id") or 0
        conversation = db.get(Conversation, conversation_id) if conversation_id else None
        if conversation is None:
            conversation = Conversation(
                user_id=state["user_id"],
                title=state["question"][:80] or "Nueva conversación",
            )
            db.add(conversation)
            db.commit()
            db.refresh(conversation)

        db.add(Message(conversation_id=conversation.id, role="user", content=state["question"]))
        db.add(
            Message(
                conversation_id=conversation.id,
                role="assistant",
                content=state.get("answer", ""),
                sources_json=json.dumps(state.get("sources", []), ensure_ascii=False),
                refused=bool(state.get("refused")),
            )
        )
        db.commit()
        return {"conversation_id": conversation.id}
    except Exception as exc:
        return {"conversation_id": state.get("conversation_id") or 0, "history_error": str(exc)}
    finally:
        db.close()


def route_after_intent(state: AgentState) -> str:
    if state.get("intent") == "meta":
        return "agent_info"
    if state.get("intent") == "catalogo":
        return "catalog_query"
    return "retrieve"


def route_after_sufficiency(state: AgentState) -> str:
    return "generate" if state.get("sufficient") else "reject"


def route_after_validation(state: AgentState) -> str:
    if not state.get("grounded") and state.get("retry_count", 0) < 1:
        return "generate"       # segundo intento con instrucción más estricta
    if not state.get("grounded"):
        # Si tras el reintento la respuesta sigue sin sostenerse, se rechaza
        return "reject"
    return "persist"


def build_graph():
    builder = StateGraph(AgentState)

    builder.add_node("validate_intent", validate_intent)
    builder.add_node("retrieve", retrieve)
    builder.add_node("evaluate_sufficiency", evaluate_sufficiency)
    builder.add_node("catalog_query", catalog_query)
    builder.add_node("agent_info", agent_info)
    builder.add_node("generate", generate)
    builder.add_node("validate_answer", validate_answer)
    builder.add_node("reject", reject)
    builder.add_node("persist", persist)

    builder.add_edge(START, "validate_intent")
    builder.add_conditional_edges(
        "validate_intent",
        route_after_intent,
        {
            "reject": "reject",
            "retrieve": "retrieve",
            "catalog_query": "catalog_query",
            "agent_info": "agent_info",
        },
    )
    builder.add_edge("retrieve", "evaluate_sufficiency")
    builder.add_conditional_edges(
        "evaluate_sufficiency", route_after_sufficiency, {"generate": "generate", "reject": "reject"}
    )
    builder.add_edge("generate", "validate_answer")
    builder.add_conditional_edges(
        "validate_answer",
        route_after_validation,
        {"generate": "generate", "reject": "reject", "persist": "persist"},
    )
    builder.add_edge("catalog_query", "persist")
    builder.add_edge("agent_info", "persist")
    builder.add_edge("reject", "persist")
    builder.add_edge("persist", END)

    return builder.compile()


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph
