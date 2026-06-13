"""Shared base class for the pipeline agents."""

from __future__ import annotations

import logging
from typing import Any

from ..providers.llm.base import LLMProvider

log = logging.getLogger(__name__)


class Agent:
    """Base agent holding a reference to the LLM provider."""

    name: str = "agent"

    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    @staticmethod
    def fetch_avoid_terms(
        vocab_mcp: Any, owner: str | None, target_language: str
    ) -> list[str]:
        """Query the learned-vocabulary MCP server for words to avoid reusing.

        Best-effort: if the MCP session is missing or the query fails, returns an
        empty list and generation proceeds normally (vocabulary avoidance is an
        optimization, never a hard requirement).
        """
        if vocab_mcp is None or not owner:
            return []
        try:
            return vocab_mcp.fetch_terms(owner=owner, target_language=target_language)
        except Exception as exc:  # noqa: BLE001 - avoidance is best-effort
            log.warning(
                "learned-vocab MCP query failed (%s); proceeding without avoidance",
                exc,
            )
            return []
