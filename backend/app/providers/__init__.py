"""Provider factories — pick a concrete provider, gracefully degrade to mocks.

Each factory honours the configured/auto-resolved provider but falls back to a
mock implementation (with a LOUD warning) if the dependency or credential is
missing, so the service always starts and the pipeline always runs.

The warnings matter: a mock LLM produces placeholder scripts and mock TTS
produces SILENT audio, so the logs make it obvious when real keys are missing.
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
        if settings.anthropic_api_key:
            try:
                from .llm.claude import ClaudeLLM

                log.info("LLM provider: Claude (model=%s)", settings.anthropic_model)
                return ClaudeLLM(
                    api_key=settings.anthropic_api_key,
                    model=settings.anthropic_model,
                    thinking=settings.anthropic_thinking,
                )
            except Exception as exc:  # pragma: no cover - defensive
                log.warning(
                    "Failed to initialise Claude LLM (%s); falling back to mock.", exc
                )
        else:
            log.warning(
                "LLM provider 'claude' selected but ANTHROPIC_API_KEY is missing; "
                "falling back to mock."
            )
    from .llm.mock import MockLLM

    log.warning(
        "LLM provider: MOCK — scripts will be PLACEHOLDER text, not real generation. "
        "Set ANTHROPIC_API_KEY to use Claude."
    )
    return MockLLM()


def get_search(settings: Settings | None = None) -> SearchProvider:
    settings = settings or get_settings()
    choice = settings.resolved_search_provider()
    if choice == "tavily":
        if settings.tavily_api_key:
            try:
                from .search.tavily import TavilySearch

                log.info("Search provider: Tavily")
                return TavilySearch(api_key=settings.tavily_api_key)
            except Exception as exc:  # pragma: no cover - defensive
                log.warning(
                    "Failed to initialise Tavily search (%s); falling back to mock.", exc
                )
        else:
            log.warning(
                "Search provider 'tavily' selected but TAVILY_API_KEY is missing; "
                "falling back to mock."
            )
    from .search.mock import MockSearch

    log.warning(
        "Search provider: MOCK — using canned sources, not real web search. "
        "Set TAVILY_API_KEY to use Tavily."
    )
    return MockSearch()


def get_tts(settings: Settings | None = None) -> TTSProvider:
    settings = settings or get_settings()
    choice = settings.resolved_tts_provider()
    if choice == "google":
        try:
            from .tts.google import GoogleTTS

            auth = "API key" if settings.google_api_key else "service-account credentials"
            log.info("TTS provider: Google Cloud TTS (%s)", auth)
            return GoogleTTS(api_key=settings.google_api_key)
        except Exception as exc:
            log.warning(
                "Failed to initialise Google Cloud TTS (%s); falling back to mock TTS. "
                "Ensure google-cloud-texttospeech is installed and the key/credentials "
                "are valid.",
                exc,
            )
    from .tts.mock import MockTTS

    log.warning(
        "TTS provider: MOCK — generated audio will be SILENT. "
        "Set GOOGLE_API_KEY or GOOGLE_APPLICATION_CREDENTIALS for real speech."
    )
    return MockTTS()
