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

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Object storage
    storage_backend: Literal["local"] = "local"
    storage_local_dir: str = "./storage"

    # LLM provider
    llm_provider: Literal["auto", "openai", "stub"] = "auto"
    openai_api_key: str = ""
    llm_model: str = "gpt-4o-mini"

    # Embeddings provider
    embeddings_provider: Literal["auto", "openai", "stub"] = "auto"
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536

    # OCR / vision provider
    ocr_provider: Literal["auto", "hf", "stub"] = "auto"
    hf_api_token: str = ""
    hf_ocr_model: str = "microsoft/trocr-base-printed"

    # External public APIs
    fema_api_base: str = "https://www.fema.gov/api/open"
    nws_api_base: str = "https://api.weather.gov"
    nominatim_api_base: str = "https://nominatim.openstreetmap.org"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
