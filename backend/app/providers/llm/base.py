"""LLM provider protocol — structured (schema-constrained) completions."""

from __future__ import annotations

from typing import Callable, Optional, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

# An MCP/tool executor: takes a tool name and its arguments, returns the text
# result to feed back to the model.
ToolExecutor = Callable[[str, dict], str]


class LLMProvider(Protocol):
    name: str

    def structured(
        self,
        *,
        system: str,
        user: str,
        schema: type[T],
        mock_example: Optional[T] = None,
        max_tokens: int = 8000,
    ) -> T:
        """Return an instance of ``schema`` produced by the model.

        Implementations that talk to a real model use ``schema`` to constrain
        the output. The mock implementation returns ``mock_example`` so agents
        can supply meaningful canned content when running without API keys.
        """
        ...

    def structured_with_tools(
        self,
        *,
        system: str,
        user: str,
        tools: list[dict],
        execute_tool: ToolExecutor,
        schema: type[T],
        mock_bootstrap: Callable[[ToolExecutor], T],
        max_tokens: int = 4000,
        max_steps: int = 3,
    ) -> T:
        """Run an agentic tool-use loop and return an instance of ``schema``.

        The model is given ``tools`` (e.g. an MCP topic-retrieval tool) and may
        call them repeatedly via ``execute_tool`` before producing the final
        schema-constrained answer. The mock implementation can't call tools, so
        it delegates to ``mock_bootstrap`` — which performs the canned tool
        call(s) and returns a meaningful result for offline runs.
        """
        ...
