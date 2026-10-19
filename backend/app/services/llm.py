"""Cliente del modelo de lenguaje con selección de proveedor.

Dos caminos según LLM_PROVIDER:

  "ollama" modelo local en el portátil (idioma de la demo local).
  "openai" API de OpenAI, para el despliegue en la nube.

El grafo espera un objeto con .invoke(...) que devuelva algo con .content.
langchain_ollama se importa solo en el camino local.
"""
from langchain_core.messages import AIMessage

from app.config import get_settings


def _get_ollama():
    from langchain_ollama import ChatOllama

    s = get_settings()
    return ChatOllama(
        base_url=s.ollama_base_url,
        model=s.ollama_model,
        temperature=s.llm_temperature,
        seed=42,           # fija la semilla: con temperature 0 la respuesta varía
        num_ctx=8192,
        # Con reasoning activo qwen3.5:4b devuelve la respuesta vacía.
        reasoning=False,
        keep_alive=s.ollama_keep_alive,
        client_kwargs={"timeout": 300.0},
    )


class _OpenAIChat:
    """Adaptador mínimo con la interfaz .invoke() que espera graph.py."""

    def __init__(self):
        s = get_settings()
        if not s.openai_api_key:
            raise RuntimeError("LLM_PROVIDER=openai pero OPENAI_API_KEY está vacío.")
        self._model = s.openai_chat_model
        self._temperature = s.llm_temperature
        self._api_key = s.openai_api_key

    def invoke(self, messages):
        import httpx

        if isinstance(messages, str):
            messages = [messages]
        payload_messages = []
        for m in messages:
            if isinstance(m, str):
                payload_messages.append({"role": "user", "content": m})
                continue
            role = getattr(m, "type", "human")
            if role in ("human", "user"):
                role = "user"
            elif role in ("ai", "assistant"):
                role = "assistant"
            else:
                role = "system"
            payload_messages.append({"role": role, "content": m.content})

        resp = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={
                "model": self._model,
                "messages": payload_messages,
                "temperature": self._temperature,
            },
            timeout=120.0,
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"] or ""
        return AIMessage(content=text)


def get_llm():
    s = get_settings()
    if s.llm_provider == "openai":
        return _OpenAIChat()
    return _get_ollama()
