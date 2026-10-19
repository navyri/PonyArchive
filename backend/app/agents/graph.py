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

# Bonus léxico cuando la pregunta nombra literalmente el título del documento
BONUS_MENCION = 0.10

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

# Recuento o enumeración del catálogo: la mención de una entidad no convierte la
# consulta en factual.
COUNT_RE = re.compile(r"enumera|numera|listado|lista|recuento", re.IGNORECASE)

# Un recuento solo lo resuelve el catálogo SQL si pregunta por un tipo que este
# conoce (episodios, capítulos, canciones, personajes, temporadas u otros
# documentos indexados). «¿Cuántas cartas tiene Moon Box 7?» pide un dato de un
# documento subido, no un recuento del corpus Pony: forzarlo al catálogo
# respondía «ningún episodio menciona a Moon Box 7» (bug del 2026-10-19).
CATALOG_COUNT_RE = re.compile(
    r"cu[aá]nt(as|os)[^.?!]{0,40}"
    r"(episodio|cap[ií]tulo|canci[oó]n|personaje|temporada|documento|fragmento|ficha)",
    re.IGNORECASE,
)

# Tipo de documento citado en la pregunta, para resolver catálogo sin depender del LLM
_DOC_TYPE_WORDS = (
    (re.compile(r"cancion|canciones|song", re.IGNORECASE), "cancion"),
    (re.compile(r"episodio|episodios|capitulo|cap[ií]tulos", re.IGNORECASE), "episodio"),
    (re.compile(r"personaje|personajes|poni|ponis", re.IGNORECASE), "personaje"),
)

# Para inferir el tipo desde la pregunta: pide listar, no describir (evita confundir
# «¿cuáles son los personajes...?» con una enumeración de catálogo)
_ENUM_TYPE_RE = re.compile(
    r"(lista|listar|enumera|enum[eé]rame|muestra|m[ué]strame|dame|menciona|nombra)"
    r"[^.?!]{0,40}(cancion|canciones|episodio|episodios|cap[ií]tulos?|personaje|personajes)",
    re.IGNORECASE,
)


def _doc_type_from_question(question: str) -> str | None:
    """Infiere el tipo de documento que la pregunta pide listar (null si no lo nombra)."""
    for enum_re in (_ENUM_TYPE_RE, _ENUM_Q_RE):
        match = enum_re.search(question)
        if not match:
            continue
        for pattern, doc_type in _DOC_TYPE_WORDS:
            if pattern.search(match.group(0)):
                return doc_type
    return None


# Verbos de enumeración que piden una lista completa (sin «cuántos», que es recuento)
_ENUM_VERBS_RE = re.compile(
    r"\b(lista|listar|enumera|enum[eé]rame|muestra|m[ué]strame|dame|menciona|nombra|cu[aá]les)\b",
    re.IGNORECASE,
)

# Misma petición sin verbo de listado («¿qué canciones de MLP existen?»): el tipo del
# catálogo va seguido de hay/existen/salen dentro de la misma frase. Se excluye «tiene»,
# que señala una pregunta por una propiedad concreta, no por un listado.
_ENUM_Q_RE = re.compile(
    r"\bqu[eé]\s+(cancion(?:es)?|episodio(?:s)?|cap[ií]tulos?|personajes|ponis|ponies)"
    r"[^.?!]{0,30}\b(hay|existe[n]?|salen|tienes)\b",
    re.IGNORECASE,
)


def _es_enumeracion(question: str) -> bool:
    """La pregunta pide listar el catálogo, en cualquiera de sus redacciones."""
    if _ENUM_VERBS_RE.search(question):
        return True
    if not _ENUM_Q_RE.search(question):
        return False
    # Un capítulo concreto acota fuera de lo que el catálogo puede filtrar
    # («¿qué personajes hay en el capítulo 47?» no es un listado del catálogo).
    return re.search(r"cap[ií]tulo\s+\d", question, re.IGNORECASE) is None

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
2. Usa la frase de rechazo SOLO si ningún fragmento menciona a la persona, cosa o tema
   de la pregunta: responde EXACTAMENTE "{refusal}" y termina con: {suggestion}
   Antes de rechazar, revisa TODOS los fragmentos completos —sinopsis, fichas y
   diálogos incluidos—. Si el asunto aparece en alguno, NO rechaces: aplica la regla 7,
   aunque los fragmentos no contesten la pregunta palabra por palabra. En preguntas
   generales de la serie («¿de qué trata la serie?», «resume de qué va MLP»), cualquier
   episodio, ficha o personaje documentado es material válido para resumir lo que la
   biblioteca dice del tema: responde con eso en lugar de rechazar.
3. Distingue siempre entre "Dato documentado:" (información literal de la fuente) e
   "Interpretación del documento:" (inferencia razonable a partir de ella). Si algo no
   aparece, di "No está documentado en la biblioteca" en lugar de rellenarlo.
4. No inventes nombres, episodios, fechas, moralejas ni relaciones entre personajes.
5. Cita las fuentes al final como [1], [2]... con título y tipo de documento.
6. Responde en español, claro y breve, pero copia los nombres propios tal como
   aparecen en los fragmentos (p. ej. "Princess Celestia", no "Princesa Celestia"):
   así quien lea puede rastrearlos en la fuente.
7. Si la pregunta trata de una persona o tema que SÍ aparece en el contexto —aunque
   pida un detalle que no consta («¿cuál es el segundo nombre de X?») o una cifra que
   los fragmentos no permiten calcular («¿cuántos episodios de X?»)—, resume lo que sí
   está documentado sobre ese asunto y termina con «No está documentado en la biblioteca:
   <lo que falta>». No rechaces por falta del dato puntual.
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
    """Minúsculas sin acentos ni puntuación (también guiones y guiones bajos:
    «cartas-kayou-mlp.txt» debe casar con «cartas kayou» en la pregunta, no
    formar un token único que impide detectar la entidad)."""
    table = str.maketrans("áéíóúüñ?¡¿.,:;!()-_", "aeiouun" + " " * 12)
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


def _tokens_entidad(question: str, user_id: int | None = None) -> set[str]:
    """Tokens (≥5) de títulos visibles que la pregunta nombra literalmente."""
    q_tokens = {t for t in _norm_text(question).split() if len(t) >= 5}
    if not q_tokens:
        return set()
    db = SessionLocal()
    try:
        query = db.query(Document.title).filter(Document.status == "indexado")
        if user_id:
            query = query.filter(
                Document.user_id.is_(None) | (Document.user_id == user_id)
            )
        else:
            query = query.filter(Document.user_id.is_(None))
        titles = [t for (t,) in query.all()]
    finally:
        db.close()
    return {
        tok
        for t in titles
        for tok in _norm_text(t).split()
        if len(tok) >= 5 and tok in q_tokens
    }


def _umbral_e1(settings, r: dict) -> float:
    """Umbral E1 aplicable al fragmento: la nota de contexto del curso usa el suyo."""
    if r.get("metadata", {}).get("doc_type") == "nota_curso":
        return settings.similarity_threshold_nota
    return settings.similarity_threshold


# Palabras que anclan la pregunta al dominio documentado de la biblioteca (MLP G4):
# el clasificador de intención (sobre todo el de la nube) a veces marca «fuera_de_
# dominio» a preguntas claramente de la serie, y «meta» a preguntas de contenido.
_DOMINIO_MLP_RE = re.compile(
    r"mlp|my little pony|friendship|equestria|poni|ponis|episodio|temporada|"
    r"personaje|magia|alicorn|everfree|cutie|pegaso|unicornio|cancion|"
    r"twilight|applejack|rainbow|pinkie|fluttershy|rarit|zecora|discord|celestia|spike",
    re.IGNORECASE,
)
# Verbos de pregunta de contenido: quien los usa quiere información, no alcance
_CONTENIDO_RE = re.compile(
    r"trata|resume|sobre\b|h[aá]blame|cu[eé]ntame|describe|explica|significa|"
    r"qu[eé] es|qu[eé] son|quien es|qui[eé]n es|quienes son",
    re.IGNORECASE,
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

    # Un recuento del catálogo («cuántos episodios hay de Rarity») se resuelve
    # con SQL: dejarlo a la recuperación semántica hace que el LLM cuente los
    # fragmentos recuperados y anuncie un número que no es el del catálogo. Solo
    # se fuerza si el recuento nombra un tipo del corpus; los recuentos de datos
    # externos («cuántas cartas tiene Moon Box 7») van a la recuperación.
    if CATALOG_COUNT_RE.search(question):
        intent = "catalogo"

    # Enumeración del catálogo en cualquier redacción («lista las canciones»,
    # «¿qué canciones existen?») y cualquier cita de temporada: se resuelven leyendo
    # la BD (E7), nunca con recuperación semántica, que solo traería fragmentos sueltos.
    if _es_enumeracion(question) or SEASON_Q_RE.search(question):
        intent = "catalogo"

    # Mención literal de un nombre documentado: corrige intenciones erróneas del
    # clasificador (meta/catalogo/fuera_de_dominio) salvo que pida un recuento del
    # corpus o un listado, que se resuelven con SQL (E7).
    entidades = _tokens_entidad(question, state.get("user_id"))
    if (
        entidades
        and intent in {"meta", "catalogo", "fuera_de_dominio", "ambigua"}
        and not (CATALOG_COUNT_RE.search(question) or COUNT_RE.search(question))
    ):
        intent = "factual"

    # Un título documentado citado en la pregunta anula un "fuera_de_dominio"
    # erróneo del clasificador (bug del 2026-10-18) y acota la recuperación.
    titulo = data["titulo"]
    if intent == "fuera_de_dominio":
        citado = _documented_title_in(question)
        if citado:
            intent, titulo = "factual", citado

    # Correcciones deterministas de clasificación errónea (observadas con el
    # clasificador de la nube): palabras del dominio MLP anulan un "fuera_de_
    # dominio" falso (T04 «sulfato de cobre» no tiene ninguna y sigue rechazando),
    # y verbos de contenido convierten un "meta" falso en factual.
    if intent == "fuera_de_dominio" and _DOMINIO_MLP_RE.search(question):
        intent = "factual"
    if intent == "meta" and _CONTENIDO_RE.search(question):
        intent = "factual"

    # La enumeración/catálogo necesita el tipo de documento; se infiere de la propia
    # pregunta y manda sobre lo que proponga el clasificador (que puede equivocarse).
    tipo = data["tipo_documento"]
    if intent == "catalogo" and _es_enumeracion(question):
        tipo = _doc_type_from_question(question) or tipo
    elif not tipo:
        tipo = _doc_type_from_question(question) or tipo

    return {
        "intent": intent,
        "theme": data["theme"],
        "title_filter": titulo,
        "doc_type_filter": tipo,
        "compare_items": data["elementos"] or [],
        "clarification": data["aclaracion"],
        "mentions": sorted(entidades),
    }


def retrieve(state: AgentState) -> dict:
    """Nodo 3: buscar información relevante en la base vectorial, con filtros."""
    question = state["question"]
    settings = get_settings()
    notes: list[str] = []
    results: list[dict] = []
    propios: list[dict] = []
    entidades = set(state.get("mentions") or [])

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
        # Dominio anclado: sin el ancla, preguntas generales («¿de qué trata la
        # serie?») devolvían episodios al azar con similitudes altas (efecto hub)
        # y el modelo terminaba negando; el ancla sube la sinopsis del piloto y
        # las fichas narrativas al top-k.
        results.extend(
            _search(f"My Little Pony: Friendship Is Magic. {question}")
        )
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
        # Fuente citada por nombre: búsqueda acotada por título para que el documento
        # que el usuario nombra entre aunque quede fuera del top-k de la general.
        # Primero por el título completo de un documento indexado; si no, por token.
        if entidades:
            db = SessionLocal()
            try:
                visibles = (
                    db.query(Document.title)
                    .filter(Document.status == "indexado")
                )
                if user_id:
                    visibles = visibles.filter(
                        Document.user_id.is_(None) | (Document.user_id == user_id)
                    )
                else:
                    visibles = visibles.filter(Document.user_id.is_(None))
                mencion = next(
                    (
                        t
                        for (t,) in visibles.all()
                        if entidades
                        & set(_norm_text(t).split())
                    ),
                    None,
                )
            finally:
                db.close()
            if mencion:
                results.extend(_search(question, title_contains=mencion))
            else:
                for tok in sorted(entidades)[:3]:
                    results.extend(_search(question, title_contains=tok))
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
    # Mención literal del nombre del documento en la pregunta: bonus léxico y marca
    # de cita que garantizan el paso de la fuente elegida por el usuario (E1 no aplica).
    if entidades:
        mencionados = 0
        for r in results:
            if entidades & set(_norm_text(r["metadata"].get("title", "")).split()):
                r["score"] = min(1.0, r["score"] + BONUS_MENCION)
                r["metadata"]["por_mencion"] = True
                mencionados += 1
        if mencionados:
            notes.append(
                f"{mencionados} fragmento(s) cuyo nombre se cita en la pregunta "
                f"(bonus +{BONUS_MENCION}, sin umbral E1)."
            )
    results.sort(key=lambda r: r["score"], reverse=True)
    seen_texts: set[str] = set()
    unique: list[dict] = []
    for r in results:
        if r["text"] not in seen_texts:
            seen_texts.add(r["text"])
            unique.append(r)
    results = unique

    # Auditoría: qué descarta el umbral (se conserva para explicar el rechazo).
    # Los fragmentos citados por nombre saltan E1: el usuario nombra la fuente.
    def _cortado(r: dict) -> bool:
        return r["score"] < _umbral_e1(settings, r) and not r["metadata"].get(
            "por_mencion"
        )

    accepted = [r for r in results if not _cortado(r)]
    rejected = [r for r in results if _cortado(r)]
    if rejected:
        notes.append(
            f"{len(rejected)} fragmento(s) descartados por similitud "
            f"bajo su umbral E1 (máximo {max(r['score'] for r in rejected):.3f})."
        )
    # Selección con diversidad: como máximo dos fragmentos por documento, para que
    # el contexto cubra fuentes distintas en lugar de trozos repetidos de un episodio.
    top: list[dict] = []
    por_doc: dict = {}
    for r in accepted:
        if len(top) >= settings.top_k:
            break
        doc_id = r["metadata"].get("doc_id")
        # La diversidad evita que un solo documento monopolice el contexto, pero
        # si el usuario lo cita por nombre quiere leer ESE documento: se le da
        # más presupuesto (bug del 2026-10-19: «¿qué rarezas tiene Moon Box 7?»
        # rechazaba porque solo 5 de 24 fragmentos del .txt subido entraban).
        limite_doc = 6 if r["metadata"].get("por_mencion") else 2
        if por_doc.get(doc_id, 0) >= limite_doc:
            continue
        por_doc[doc_id] = por_doc.get(doc_id, 0) + 1
        top.append(r)
    # Las fuentes citadas por nombre no se recortan: el usuario nombra la fuente.
    extra = [
        r
        for r in accepted
        if r["metadata"].get("por_mencion") and r not in top
    ]
    if extra:
        top.extend(extra[:3])
    if top:
        notes.append(f"Similitud máxima: {max(r['score'] for r in top):.3f}.")

    return {"retrieved": top, "retrieval_notes": notes}


def evaluate_sufficiency(state: AgentState) -> dict:
    """Nodos 4 y 6 (estrategias E1 y E2): decide si el contexto permite responder."""
    settings = get_settings()
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

    mejor = max(retrieved, key=lambda r: r["score"])
    umbral_mejor = _umbral_e1(settings, mejor)
    # Una fuente citada por nombre sostiene la consulta aunque su similitud quede
    # baja: el usuario la nombra explícitamente en la pregunta.
    citada = any(r["metadata"].get("por_mencion") for r in retrieved)
    if mejor["score"] < umbral_mejor and not citada:
        return {
            "sufficient": False,
            "refusal_reason": f"La similitud máxima ({mejor['score']:.3f}) es inferior al umbral ({umbral_mejor}).",
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


def _episodes_mentioning(nombre: str) -> list[str]:
    """Títulos de episodios cuyo texto menciona al personaje citado, sin LLM.

    Cuenta cada episodio una vez agrupando por documento; la mención se busca en
    cualquier fragmento del episodio, no solo en el título.
    """
    patron = re.compile(re.escape(nombre), re.IGNORECASE)
    por_doc: dict[int, tuple[str, bool]] = {}
    for item in fetch_documents("episodio"):
        meta = item.get("metadata", {})
        doc_id = meta.get("doc_id")
        if doc_id is None:
            continue
        titulo = meta.get("title", "")
        mencionado = patron.search(item.get("text") or "") is not None
        if doc_id in por_doc:
            prev_titulo, prev_menc = por_doc[doc_id]
            por_doc[doc_id] = (prev_titulo, prev_menc or mencionado)
        else:
            por_doc[doc_id] = (titulo, mencionado)
    return sorted(t for t, menc in por_doc.values() if menc)


def _catalog_titles(doc_type: str) -> list[str]:
    """Títulos indexados de un tipo de documento, leídos de la BD sin LLM."""
    db = SessionLocal()
    try:
        return [
            t
            for (t,) in db.query(Document.title)
            .filter(Document.status == "indexado", Document.doc_type == doc_type)
            .order_by(Document.title)
            .all()
        ]
    finally:
        db.close()


SEASON_IN_TEXT_RE = re.compile(r"Temporada (\d+), episodio", re.IGNORECASE)


def _titles_by_season(season: int) -> list[str]:
    """Títulos de episodios de una temporada, detectados en el texto sin LLM."""
    seen: dict[int, tuple[str, int]] = {}
    for item in fetch_documents("episodio"):
        meta = item.get("metadata", {})
        doc_id = meta.get("doc_id")
        if doc_id is None or doc_id in seen:
            continue
        match = SEASON_IN_TEXT_RE.search(item.get("text") or "")
        if match and int(match.group(1)) == season:
            seen[doc_id] = (meta.get("title", ""), 0)
    return sorted(t for t, _ in seen.values())


def _episodes_by_season() -> tuple[dict[int, list[str]], list[str]]:
    """Títulos de episodios agrupados por temporada y especiales, sin LLM.

    La temporada se lee de la cabecera documental («Temporada N, episodio M»);
    los especiales (películas y Equestria Girls) no llevan número de temporada.
    """
    docs: dict[int, dict] = {}
    for item in fetch_documents("episodio"):
        meta = item.get("metadata", {})
        doc_id = meta.get("doc_id")
        if doc_id is None:
            continue
        info = docs.setdefault(doc_id, {"title": meta.get("title", ""), "season": None})
        if not info["title"] and meta.get("title"):
            info["title"] = meta["title"]
        if info["season"] is None:
            match = SEASON_IN_TEXT_RE.search(item.get("text") or "")
            if match:
                info["season"] = int(match.group(1))
    agrupados: dict[int, list[str]] = {}
    especiales: list[str] = []
    for info in docs.values():
        if info["season"]:
            agrupados.setdefault(info["season"], []).append(info["title"])
        else:
            especiales.append(info["title"])
    return (
        {temp: sorted(tits) for temp, tits in sorted(agrupados.items())},
        sorted(especiales),
    )


# Temporada citada en la pregunta («episodios de la temporada 3», «temporada tres»)
SEASON_Q_RE = re.compile(
    r"temporada\s+(\d+|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve)",
    re.IGNORECASE,
)
_SEASON_WORDS = {
    "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9,
}


def _season_number(match: re.Match | None) -> int | None:
    """Número de temporada desde un coincidence de SEASON_Q_RE (dígito o palabra)."""
    if not match:
        return None
    token = match.group(1).lower()
    return int(token) if token.isdigit() else _SEASON_WORDS.get(token)


def catalog_query(state: AgentState) -> dict:
    """Estrategia E7: consultas estructuradas para contar o enumerar el catálogo.

    Enumerar («lista las canciones») devuelve los títulos reales de la BD; contar
    («cuántas canciones») devuelve el resumen por tipo. Ni LLM ni invención.
    """
    question = state.get("question", "")
    tipo = (state.get("doc_type_filter") or "").strip().lower()
    notes: list[str] = []

    season_m = SEASON_Q_RE.search(question)
    season_n = _season_number(season_m)
    por_temporada = (
        re.search(r"por\s+temporadas?", question, re.IGNORECASE) is not None
    )
    es_conteo = re.search(r"cu[aá]nt(as|os)\b", question, re.IGNORECASE) is not None

    # En esta biblioteca las temporadas organizan los capítulos: una cita de
    # temporada sin tipo explícito («cuéntame de la temporada 3») se resuelve por
    # episodios, salvo que la pregunta nombre otro tipo («canciones de la 2»).
    if not tipo and (season_n or por_temporada):
        tipo = next(
            (dt for pat, dt in _DOC_TYPE_WORDS if pat.search(question)),
            "episodio",
        )

    titulo = (state.get("title_filter") or "").strip()
    # El clasificador puede confundir «temporada 3» con un título citado: no lo es.
    if season_n and _norm_text(titulo).startswith("temporada"):
        titulo = ""

    # Recuento acotado a una entidad citada («cuántos episodios hay de Rarity»):
    # se cuenta desde el texto documental, no desde los fragmentos recuperados.
    # Solo aplica a episodios/capítulos: la rama asumía «episodio» por defecto y
    # respondía «ningún episodio menciona a Moon Box 7» a preguntas sobre cartas
    # (bug del 2026-10-19).
    if titulo and es_conteo and (
        _doc_type_from_question(question) == "episodio"
        or re.search(r"episodio|cap[ií]tulo", question, re.IGNORECASE)
    ):
        mencionados = _episodes_mentioning(titulo)
        if mencionados:
            lines = [
                "Dato documentado (consulta directa al catálogo, no por similitud):"
            ]
            lines.append(
                f"La biblioteca documenta {len(mencionados)} episodio(s) donde "
                f"se menciona a {titulo}:"
            )
            lines.extend(f"- {t}" for t in mencionados)
            return {"answer": "\n".join(lines), "sources": [], "refused": False}
        # Sin coincidencias: se advierte en vez de inventar un número.
        lines = [
            "Dato documentado (consulta directa al catálogo, no por similitud):"
        ]
        lines.append(
            f"No se documenta ningún episodio que mencione a {titulo}; el "
            f"catálogo no permite responder cuántos episodios hay de esa entidad."
        )
        return {"answer": "\n".join(lines), "sources": [], "refused": False}

    # Recuento por temporada («cuántos capítulos tiene la temporada 3»): la cifra y
    # el listado salen del texto documental, sin LLM ni invención.
    if season_n and tipo == "episodio" and es_conteo:
        titulos = _titles_by_season(season_n)
        lines = ["Dato documentado (consulta directa al catálogo, no por similitud):"]
        if titulos:
            lines.append(f"La temporada {season_n} documenta {len(titulos)} capítulos:")
            lines.extend(f"- {t}" for t in titulos)
        else:
            lines.append(
                f"La temporada {season_n} no consta documentada en el catálogo de episodios."
            )
        return {"answer": "\n".join(lines), "sources": [], "refused": False}

    # Listado agrupado por temporadas («lista los capítulos por temporada»): secciones
    # por temporada en vez de una lista plana de todos los capítulos.
    if por_temporada and not season_n and tipo == "episodio":
        agrupados, especiales = _episodes_by_season()
        if agrupados:
            lines = ["Dato documentado (consulta directa al catálogo, no por similitud):"]
            total_caps = 0
            for temp, tits in agrupados.items():
                total_caps += len(tits)
                lines.append(f"Temporada {temp} ({len(tits)} capítulos):")
                lines.extend(f"- {t}" for t in tits)
                lines.append("")
            if especiales:
                lines.append(f"Especiales sin número de temporada ({len(especiales)}):")
                lines.extend(f"- {t}" for t in especiales)
                lines.append("")
            lines.append(
                f"Total: {total_caps} capítulos numerados en {len(agrupados)} temporadas."
            )
            return {"answer": "\n".join(lines), "sources": [], "refused": False}

    # Enumeración solo si la pregunta pide listar Y se identificó el tipo de
    # documento; sin tipo válido cae al recuento por tipo (sin inventar nada).
    # Una cita de temporada fuerza el listado de ESE temporada aunque la redacción
    # no traiga verbo de listado («¿qué capítulos tiene la temporada 5?»).
    enum = (_es_enumeracion(question) or bool(season_n)) and bool(tipo)
    if enum:
        if season_n and tipo == "episodio":
            titulos = _titles_by_season(season_n)
            etiqueta = f"episodios de la temporada {season_n}"
            if not titulos:
                lines = [
                    "Dato documentado (consulta directa al catálogo, no por similitud):",
                    f"La temporada {season_n} no consta documentada en el catálogo "
                    "de episodios.",
                ]
                return {"answer": "\n".join(lines), "sources": [], "refused": False}
        else:
            # Solo se anuncia el filtro de temporada si realmente se aplica: los
            # episodios tienen temporada en el texto, el resto de tipos no.
            if season_n:
                notes.append(
                    "La temporada citada no consta indexada para este tipo de "
                    "documento; se lista el tipo completo."
                )
            titulos = _catalog_titles(tipo)
            etiqueta = f"elemento(s) de tipo '{tipo}'"
        if titulos:
            lines = [f"Dato documentado (consulta directa al catálogo, no por similitud):"]
            lines.append(f"La biblioteca documenta {len(titulos)} {etiqueta}:")
            lines.extend(f"- {t}" for t in titulos)
            if notes:
                lines.append("")
                lines.extend(f"Nota: {n}" for n in notes)
            return {"answer": "\n".join(lines), "sources": [], "refused": False}

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

    # Desglose de episodios por temporada: se extrae del texto documental, sin LLM
    linea_temporadas = None
    if any(dt == "episodio" for dt, _ in rows):
        conteos, especiales = _season_breakdown()
        if conteos:
            detalle = ", ".join(
                f"Temporada {t}: {c}" for t, c in sorted(conteos.items())
            )
            linea_temporadas = (
                f"My Little Pony: Friendship Is Magic está documentada en "
                f"{len(conteos)} temporadas con {sum(conteos.values())} "
                f"capítulos numerados — {detalle}."
            )
            if especiales:
                linea_temporadas += (
                    f" Además hay {especiales} especiales (películas y Equestria Girls) "
                    f"sin número de temporada."
                )

    # Quien pregunta «cuántas temporadas» quiere ese desglose, no el volcado por tipo:
    # el desglose se responde primero (el resto de líneas sigue disponibles detrás).
    if linea_temporadas and SEASON_COUNT_RE.search(question):
        lines.append(linea_temporadas)

    for doc_type, count in sorted(rows, key=lambda r: -r[1]):
        lines.append(f"- {count} documento(s) de tipo '{doc_type}'.")
    lines.append(f"Total indexado: {total} documentos.")
    if linea_temporadas and not SEASON_COUNT_RE.search(question):
        lines.append(linea_temporadas)
    return {"answer": "\n".join(lines), "sources": [], "refused": False}


def agent_info(state: AgentState) -> dict:
    """Respuesta fija sobre el alcance del agente (sin LLM ni recuperación)."""
    return {"answer": AGENT_SCOPE, "sources": [], "refused": False}


# Términos frecuentes en las preguntas que no identifican el asunto por sí solos
_ASUNTO_STOP = {
    "quienes", "quien", "cuales", "cuanto", "cuantos", "cuantas", "donde",
    "despues", "antes", "ahora", "tambien", "sobre", "entre", "durante",
    "aparece", "aparecen", "existe", "existen", "puedes", "puede", "quiero",
    "documento", "documentos", "biblioteca", "pregunta", "respuesta",
    # «secondary»/«secundario» y compañía: con prefijo dispararían T05 sin información
    "secundario", "secundarios", "primaria", "primero",
}
# Palabras propias del dominio: presentes en casi cualquier fragmento, no distinguen
_ASUNTO_GENERICOS = {
    "temporada", "temporadas", "episodio", "episodios", "personaje", "personajes",
    "cancion", "canciones", "capitulo", "capitulos", "serie", "historia",
}


def _context_toca_el_asunto(question: str, retrieved: list[dict]) -> bool:
    """¿Algún término propio de la pregunta aparece en el contexto recuperado?

    Si el contexto nombra el asunto y el modelo aun así niega, se le da una segunda
    oportunidad con la regla 7 (resumir lo documentado y marcar el hueco). Cubre
    además el puente entre idiomas («alicornios» → «Alicorn») mediante prefijos de
    7+ letras. Los términos genéricos no cuentan: una pregunta sin evidencia real
    (T05: «capítulo 47 con un sombrero morado») no debe disparar el reintento.
    """
    if not retrieved:
        return False
    context = _norm_text(" ".join(r["text"] for r in retrieved))
    for tok in _norm_text(question).split():
        if len(tok) < 6 or tok in _ASUNTO_GENERICOS or tok in _ASUNTO_STOP:
            continue
        if tok in context:
            return True
        # Prefijos largos: «alicornios» comparte «alicorn» con el corpus en inglés
        if len(tok) >= 9 and any(tok[:n] in context for n in range(7, len(tok) - 1)):
            return True
    return False


def generate(state: AgentState) -> dict:
    """Nodo 5: responder con base en la información encontrada (estrategia E3)."""
    retrieved = state.get("retrieved", [])
    extra_rule = ""
    if state.get("retry_count", 0) > 0:
        extra_rule = (
            "8. CORRECCIÓN: tu respuesta anterior usaba entidades que no aparecen en el contexto. "
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
    mencion = next(
        (r for r in retrieved if r["metadata"].get("por_mencion")), None
    )
    toca = _context_toca_el_asunto(state["question"], retrieved)
    if refused and mencion:
        # La fuente citada está en el contexto: el rechazo no procede (reintento).
        answer = get_llm().invoke(
            prompt
            + "\n\nCORRECCIÓN OBLIGATORIA: el usuario nombra en su pregunta un documento "
            "que SÍ está en el contexto. PROHIBIDO empezar con la frase de rechazo. "
            "Escribe «Dato documentado:» con lo que ese documento tiene sobre el asunto "
            "(aunque no conteste el dato puntual) y termina con «No está documentado en "
            "la biblioteca: <el dato puntual preguntado>».\n"
        ).content.strip()
        refused = answer.startswith(REFUSAL_MESSAGE)
    if refused and toca:
        # El contexto sí nombra el asunto (p. ej. «los Elementos» en las sinopsis, o
        # «Alicorn» en inglés para «alicornios»): el rechazo total pierde lo
        # documentado; se aplica la regla 7 (reintento único).
        answer = get_llm().invoke(
            prompt
            + "\n\nCORRECCIÓN OBLIGATORIA: el contexto SÍ nombra el asunto de la pregunta "
            "(revisa cada fragmento completo, sinopsis y fichas incluidas). PROHIBIDO "
            "empezar con la frase de rechazo: resume con «Dato documentado:» lo que los "
            "fragmentos dicen sobre ese asunto y cierra con «No está documentado en la "
            "biblioteca: <lo que falta>». Si el dato puntual no aparece, márcalo con esa "
            "frase; no rechaces de plano.\n"
        ).content.strip()
        refused = answer.startswith(REFUSAL_MESSAGE)
    if refused and toca:
        # Tercer intento con prompt compacto: el prompt completo con todas las reglas
        # a veces confunde al clasificador/generador de la nube; una instrucción breve
        # y directa funciona mejor (T04/T05 no llegan aquí: toca es False para ellos).
        answer = get_llm().invoke(
            "Eres PonyArchive, un agente que responde SOLO con sus fragmentos "
            "documentales.\n\nFRAGMENTOS:\n"
            + _context_blocks(retrieved)
            + f"\nPREGUNTA: {state['question']}\n\n"
            "INSTRUCCIÓN FINAL: los fragmentos SÍ tratan el asunto de la pregunta. "
            "Resume en pocas frases lo que dicen, empezando por «Dato documentado:». "
            "Si el dato puntual no aparece, termina con «No está documentado en la "
            "biblioteca: <lo que falta>». PROHIBIDO empezar con «No tengo suficiente "
            "información».\n"
        ).content.strip()
        refused = answer.startswith(REFUSAL_MESSAGE)
    if refused and mencion:
        # Último recurso determinista: el usuario nombró un documento que está en el
        # contexto y el modelo insiste en rechazar. Se aplica la regla 7 a mano para
        # no perder lo documentado (T04/T05 no nombran ningún documento, no llegan
        # a esta rama y siguen rechazando).
        fragmento = " ".join((mencion["text"] or "").split())[:500]
        answer = (
            f"Dato documentado (del documento citado en tu pregunta): {fragmento}…\n\n"
            "No está documentado en la biblioteca: el dato puntual que se pregunta; "
            "lo demás sí está respaldado por el documento citado."
        )
        refused = False
    elif refused and toca and retrieved:
        # Mismo respaldo para el caso «asunto en el contexto»: se cita el fragmento
        # recuperado de mayor similitud en lugar de perder lo documentado.
        fragmento = " ".join((retrieved[0]["text"] or "").split())[:500]
        answer = (
            f"Dato documentado (fragmento recuperado por tu pregunta): {fragmento}…\n\n"
            "No está documentado en la biblioteca: el dato puntual que se pregunta."
        )
        refused = False
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
