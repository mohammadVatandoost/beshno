"""Application configuration loaded from environment variables / .env file."""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Database -----------------------------------------------------------
    database_url: str = "postgresql+psycopg://beshno:beshno@localhost:5433/beshno"

    # --- LLM (Anthropic / Claude) ------------------------------------------
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-opus-4-8"
    # auto | claude | mock
    llm_provider: str = "auto"

    # --- Search / retrieval -------------------------------------------------
    # auto | tavily | mock
    search_provider: str = "auto"
    tavily_api_key: str | None = None
    search_max_results: int = 10

    # --- Text to speech -----------------------------------------------------
    # auto | google | mock
    tts_provider: str = "auto"
    # Path to a Google service-account JSON (also read by the google client lib
    # via GOOGLE_APPLICATION_CREDENTIALS).
    google_application_credentials: str | None = None
    # Alternatively, a Google API key for Text-to-Speech (no service account).
    google_api_key: str | None = None

    # --- Pipeline behaviour -------------------------------------------------
    # Number of evaluator-driven revision cycles before giving up / flagging.
    max_revisions: int = 2
    # Step budget for an agent's tool-use loop (e.g. Agent 1's MCP topic
    # retrieval): the max number of LLM turns before a final answer is forced.
    # Use >= 2 so the agent gets at least one tool call before answering.
    agent_max_steps: int = 3

    # --- Storage ------------------------------------------------------------
    storage_dir: str = "./storage"

    # --- HTTP / CORS --------------------------------------------------------
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # ----------------------------------------------------------------------
    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def resolved_llm_provider(self) -> str:
        """Resolve 'auto' to a concrete provider based on available credentials."""
        if self.llm_provider != "auto":
            return self.llm_provider
        return "claude" if self.anthropic_api_key else "mock"

    def resolved_search_provider(self) -> str:
        if self.search_provider != "auto":
            return self.search_provider
        return "tavily" if self.tavily_api_key else "mock"

    def resolved_tts_provider(self) -> str:
        if self.tts_provider != "auto":
            return self.tts_provider
        creds = self.google_application_credentials or os.getenv(
            "GOOGLE_APPLICATION_CREDENTIALS"
        )
        return "google" if (self.google_api_key or creds) else "mock"


@lru_cache
def get_settings() -> Settings:
    return Settings()
