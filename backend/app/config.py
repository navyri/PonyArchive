"""Configuración central de PonyArchive.

Todas las variables se leen del entorno (o de un archivo .env). Ningún valor
secreto está escrito aquí: ver .env.example para la lista completa de variables.
"""
from functools import lru_cache
from pathlib import Path

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

    # --- Embeddings locales ---
    embedding_model: str = "intfloat/multilingual-e5-small"

    # --- Base de datos vectorial ---
    vector_dir: str = str(BACKEND_DIR / "vectorstore")
    collection_name: str = "ponyarchive"
    top_k: int = 6
    # Umbral mínimo de similitud coseno para aceptar un fragmento (estrategia anti-alucinación 1).
    # Calibrado con pruebas reales; ver docs/pruebas.md
    similarity_threshold: float = 0.62

    # --- Persistencia relacional ---
    data_dir: str = str(BACKEND_DIR / "data")
    database_url: str = f"sqlite:///{BACKEND_DIR / 'data' / 'ponyarchive.db'}"

    # --- Carga de documentos ---
    max_upload_mb: int = 20
    chunk_size: int = 900
    chunk_overlap: int = 150

    # --- Integración externa ---
    pony_api_url: str = "https://ponyapi.net/v1"

    # --- CORS (lista de orígenes permitidos, separados por coma) ---
    # 5173: puerto habitual de Vite; 5174: usado cuando el 5173 lo ocupa otro contenedor.
    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:5174,http://127.0.0.1:5174"
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
