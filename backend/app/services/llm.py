"""Cliente del modelo de lenguaje local (Ollama) mediante LangChain."""
from langchain_ollama import ChatOllama

from app.config import get_settings


def get_llm() -> ChatOllama:
    """Devuelve el modelo local configurado.

    DEC-12: modelo principal qwen3.5:4b (67 tok/s en la RTX 4070 de 8 GB).
      * `keep_alive` evita recargar el modelo (unos 20 s) entre preguntas.
      * `reasoning=False` desactiva el modo thinking de qwen3.5: sin él, el modelo
        consume el contexto razonando y devuelve la respuesta vacía (bug
        reproducido el 2026-10-17 con num_ctx=4096).
      * `num_ctx=8192` deja margen para varias fichas de contexto.
    """
    s = get_settings()
    return ChatOllama(
        base_url=s.ollama_base_url,
        model=s.ollama_model,
        temperature=s.llm_temperature,   # 0 = máxima fidelidad al contexto
        num_ctx=8192,
        reasoning=False,
        keep_alive=s.ollama_keep_alive,
        client_kwargs={"timeout": 300.0},
    )
