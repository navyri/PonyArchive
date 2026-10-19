"""Configuración central de PonyArchive.

Variables leídas del entorno o de backend/.env (ver .env.example)."""
from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Aplicación ---
    app_name: str = "PonyArchive"
    app_env: str = "dev"              # dev | prod
    api_prefix: str = "/api"

    # --- Seguridad (JWT propio) ---
    secret_key: str = "cambiar-en-produccion"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7

    # --- Autenticación: "local" (JWT propio) o "keycloak" ---
    auth_provider: str = "local"
    keycloak_url: str = "http://localhost:8080"
    keycloak_realm: str = "ponyarchive"
    keycloak_client_id: str = "ponyarchive-backend"
    keycloak_client_secret: str = ""

    # --- Modelo local (Ollama) ---
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3.5:4b"
    ollama_keep_alive: str = "30m"    # evita recargar el modelo entre preguntas
    llm_temperature: float = 0.0      # 0 = menos inventiva, más fiel al contexto
    llm_max_tokens: int = 700

    embeddings_provider: str = "local"   # local | openai
    llm_provider: str = "ollama"         # ollama | openai
    vector_provider: str = "chroma"      # chroma | qdrant

    embedding_model: str = "intfloat/multilingual-e5-small"

    openai_api_key: str = ""
    openai_chat_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dims: int = 1536

    qdrant_url: str = ""
    qdrant_api_key: str = ""
    qdrant_collection: str = "ponyarchive"

    vector_dir: str = str(BACKEND_DIR / "vectorstore")
    collection_name: str = "ponyarchive"
    top_k: int = 6
    # Anti-alucinación E1. None = calibrado por el espacio de embeddings activo:
    # la similitud coseno no es comparable entre modelos.
    similarity_threshold: float | None = None
    similarity_threshold_nota: float | None = None

    # --- Persistencia relacional ---
    data_dir: str = str(BACKEND_DIR / "data")
    database_url: str = f"sqlite:///{BACKEND_DIR / 'data' / 'ponyarchive.db'}"

    # --- Carga de documentos ---
    max_upload_mb: int = 20
    chunk_size: int = 900
    chunk_overlap: int = 150

    # --- Integración externa ---
    pony_api_url: str = "https://ponyapi.net/v1"
    import_on_start: bool = False  # importa el catálogo al arrancar si la base está vacía

    # --- CORS (lista de orígenes permitidos, separados por coma) ---
    # 5173: puerto habitual de Vite; 5174: usado cuando el 5173 lo ocupa otro contenedor.
    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:5174,http://127.0.0.1:5174"
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @model_validator(mode="after")
    def _umbral_similitud(self):
        """Umbral E1 por defecto según el espacio de embeddings activo."""
        if self.similarity_threshold is None:
            # e5 local: relevante ~0.65-0.90; OpenAI: relevante ~0.55-0.80,
            # sin evidencia ~0.45, ajeno ~0.20 (batería T01/T05/T11 del smoke).
            self.similarity_threshold = (
                0.50 if self.embeddings_provider == "openai" else 0.62
            )
        if self.similarity_threshold_nota is None:
            # La nota de contexto del curso es un documento corto y de confianza
            # explícita: con OpenAI sus preguntas de variación rondan 0.47-0.60,
            # así que se le asigna umbral propio sin relajar el resto (T05 0.455
            # sigue rechazando: la nota no entra ni en su top-20).
            self.similarity_threshold_nota = (
                0.45 if self.embeddings_provider == "openai" else self.similarity_threshold
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
