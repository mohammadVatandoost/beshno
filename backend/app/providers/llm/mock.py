"""Mock LLM provider — echoes the agent-supplied canned example.

Lets the entire multi-agent pipeline run end-to-end with no API keys.
"""

from __future__ import annotations

from typing import Callable, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

ToolExecutor = Callable[[str, dict], str]


class MockLLM:
    name = "mock"

    def structured(
        self,
        *,
        system: str,
        user: str,
        schema: type[T],
        mock_example: Optional[T] = None,
        max_tokens: int = 8000,
    ) -> T:
        if mock_example is not None:
            return mock_example
        # Best-effort construction when no example was supplied.
        try:
            return schema()  # type: ignore[call-arg]
        except Exception:
            return schema.model_construct()

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
        # The mock can't reason about tools — let the caller drive a canned
        # tool call and assemble the result. This keeps the MCP retrieval path
        # exercised end-to-end even without API keys.
        return mock_bootstrap(execute_tool)
