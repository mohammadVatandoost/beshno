"""Mock LLM provider — echoes the agent-supplied canned example.

Lets the entire multi-agent pipeline run end-to-end with no API keys. It also
records *estimated* token usage (~4 chars/token) into the run's telemetry
recorder, so the analytics feature is demonstrable on the zero-key demo. Real
token counts come from the Claude provider.
"""

from __future__ import annotations

from typing import Callable, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

ToolExecutor = Callable[[str, dict], str]


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _safe_json(model: BaseModel) -> str:
    try:
        return model.model_dump_json()
    except Exception:  # pragma: no cover - model_construct edge cases
        return ""


class MockLLM:
    name = "mock"
    # Optional per-run telemetry recorder, attached by the orchestrator.
    _recorder = None

    def _record(self, system: str, user: str, result: BaseModel) -> None:
        rec = getattr(self, "_recorder", None)
        if rec is not None:
            rec.record(
                _estimate_tokens(system + user), _estimate_tokens(_safe_json(result))
            )

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
            result: T = mock_example
        else:
            # Best-effort construction when no example was supplied.
            try:
                result = schema()  # type: ignore[call-arg]
            except Exception:
                result = schema.model_construct()
        self._record(system, user, result)
        return result

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
        result = mock_bootstrap(execute_tool)
        self._record(system, user, result)
        return result
