"""Shared base class for the pipeline agents."""

from __future__ import annotations

from ..providers.llm.base import LLMProvider


class Agent:
    """Base agent holding a reference to the LLM provider."""

    name: str = "agent"

    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm
