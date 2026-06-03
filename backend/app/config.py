"""Centralised, validated configuration.

Using pydantic-settings means every environment variable is parsed and
type-checked once, at startup, instead of being read ad-hoc with `os.getenv`
scattered across the codebase. Bad config fails fast and loudly — a production
instinct interviewers look for.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # ---- LLM provider ----
    google_api_key: str = Field(default="", description="Gemini API key (free tier).")
    model_cheap: str = "gemini-2.5-flash-lite"
    model_strong: str = "gemini-2.5-flash"
    embedding_model: str = "text-embedding-004"

    # ---- Vector store ----
    vector_backend: Literal["faiss", "pgvector"] = "faiss"
    faiss_index_dir: str = "data/index"
    database_url: str = ""

    # ---- Retrieval tuning ----
    retrieval_top_k: int = 8
    rerank_top_n: int = 4
    chunk_target_tokens: int = 800
    chunk_overlap_tokens: int = 100

    # ---- Observability ----
    log_dir: str = "backend/app/observability/logs"
    log_level: str = "INFO"

    # ---- App ----
    max_upload_mb: int = 15
    cors_origins: str = "http://localhost:5173"
    env: Literal["local", "staging", "production"] = "local"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def has_llm_credentials(self) -> bool:
        """Lets the app boot for tests/UI even without a key (degraded mode)."""
        return bool(self.google_api_key)


@lru_cache
def get_settings() -> Settings:
    """Cached singleton — import this everywhere instead of constructing Settings."""
    return Settings()
