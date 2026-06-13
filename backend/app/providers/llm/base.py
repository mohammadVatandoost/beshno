"""LLM provider protocol — structured (schema-constrained) completions."""

from __future__ import annotations

from typing import Optional, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


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
