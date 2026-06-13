"""Provider factories — pick a concrete provider, gracefully degrade to mocks.

Each factory honours the configured/auto-resolved provider but falls back to a
mock implementation (with a logged warning) if the dependency or credential is
missing, so the service always starts and the pipeline always runs.
"""

from __future__ import annotations

import logging

from ..config import Settings, get_settings
from .llm.base import LLMProvider
from .search.base import SearchProvider
from .tts.base import TTSProvider

log = logging.getLogger(__name__)


def get_llm(settings: Settings | None = None) -> LLMProvider:
    settings = settings or get_settings()
    choice = settings.resolved_llm_provider()
    if choice == "claude":
        if not settings.anthropic_api_key:
            log.warning(
                "LLM provider 'claude' selected but ANTHROPIC_API_KEY is missing; "
                "using mock LLM."
            )
        else:
            try:
                from .llm.claude import ClaudeLLM

                return ClaudeLLM(
                    api_key=settings.anthropic_api_key, model=settings.anthropic_model
                )
            except Exception as exc:  # pragma: no cover - defensive
                log.warning("Failed to initialise Claude LLM (%s); using mock.", exc)
    from .llm.mock import MockLLM

    return MockLLM()


def get_search(settings: Settings | None = None) -> SearchProvider:
    settings = settings or get_settings()
    choice = settings.resolved_search_provider()
    if choice == "tavily":
        if not settings.tavily_api_key:
            log.warning(
                "Search provider 'tavily' selected but TAVILY_API_KEY is missing; "
                "using mock search."
            )
        else:
            try:
                from .search.tavily import TavilySearch

                return TavilySearch(api_key=settings.tavily_api_key)
            except Exception as exc:  # pragma: no cover - defensive
                log.warning("Failed to initialise Tavily search (%s); using mock.", exc)
    from .search.mock import MockSearch

    return MockSearch()


def get_tts(settings: Settings | None = None) -> TTSProvider:
    settings = settings or get_settings()
    choice = settings.resolved_tts_provider()
    if choice == "google":
        try:
            from .tts.google import GoogleTTS

            return GoogleTTS(api_key=settings.google_api_key)
        except Exception as exc:
            log.warning(
                "Failed to initialise Google Cloud TTS (%s); using mock TTS. "
                "Ensure GOOGLE_APPLICATION_CREDENTIALS points to a valid "
                "service-account JSON and google-cloud-texttospeech is installed.",
                exc,
            )
    from .tts.mock import MockTTS

    return MockTTS()
