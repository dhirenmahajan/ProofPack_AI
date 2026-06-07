"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Core
    app_env: str = "development"
    log_level: str = "INFO"

    # Database
    postgres_user: str = "proofpack"
    postgres_password: str = "proofpack"
    postgres_db: str = "proofpack"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    # Optional full DSN override (e.g. Supabase pooled connection string).
    database_url_override: str = ""

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Object storage
    storage_backend: Literal["local", "s3"] = "local"
    storage_local_dir: str = "./storage"
    # S3 / R2 / MinIO (S3-compatible)
    s3_endpoint_url: str = ""
    s3_region: str = "auto"
    s3_bucket: str = "proofpack"
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""

    # Ingestion execution mode. "sync" runs inside the request (simple/local);
    # "async" enqueues a Celery task (scalable/prod).
    ingest_mode: Literal["sync", "async"] = "sync"

    # --- LLM provider ---
    # auto-priority when "auto": gemini key -> openai key -> stub.
    llm_provider: Literal["auto", "gemini", "openai", "stub"] = "auto"
    llm_model: str = "gpt-4o-mini"  # used only when the OpenAI provider is active

    # Google Gemini (free tier) — primary hosted provider.
    gemini_api_key: str = ""
    gemini_llm_model: str = "gemini-2.5-flash"
    gemini_embedding_model: str = "gemini-embedding-001"

    # OpenAI (optional)
    openai_api_key: str = ""

    # --- Embeddings provider ---
    embeddings_provider: Literal["auto", "gemini", "openai", "stub"] = "auto"
    embedding_model: str = "text-embedding-3-small"  # OpenAI model name
    # gemini-embedding-001 requested at output dim 768. The Chunk.embedding column binds
    # this value at import time; changing it invalidates already-stored vectors.
    embedding_dim: int = 768

    # --- OCR / vision provider ---
    # auto-priority when "auto": gemini key -> hf token -> tesseract (if available) -> stub.
    ocr_provider: Literal["auto", "gemini", "hf", "tesseract", "stub"] = "auto"
    hf_api_token: str = ""
    hf_ocr_model: str = "microsoft/trocr-base-printed"
    gemini_vision_model: str = "gemini-2.5-flash"
    tesseract_cmd: str = ""  # optional explicit path to the tesseract binary

    # --- External public APIs (no auth required) ---
    fema_api_base: str = "https://www.fema.gov/api/open"
    nws_api_base: str = "https://api.weather.gov"
    nominatim_api_base: str = "https://nominatim.openstreetmap.org"
    # NWS + Nominatim require a descriptive User-Agent with contact info.
    external_user_agent: str = "ProofPackAI/1.0 (contact: ops@proofpack.example)"
    external_cache_ttl_seconds: int = 86400

    # --- Observability (optional) ---
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"
    tracing_enabled: bool = False

    @property
    def database_url(self) -> str:
        if self.database_url_override:
            url = self.database_url_override
        else:
            url = (
                f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
            )
        # Railway/Supabase often provide postgresql:// DSNs; psycopg3 needs +psycopg.
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
