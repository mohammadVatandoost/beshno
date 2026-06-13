"""Mock LLM provider — echoes the agent-supplied canned example.

Lets the entire multi-agent pipeline run end-to-end with no API keys.
"""

from __future__ import annotations

from typing import Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


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
