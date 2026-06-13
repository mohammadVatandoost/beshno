"""Claude (Anthropic) LLM provider using structured outputs.

Uses ``messages.stream`` with ``output_config.format`` and a constraint-stripped
schema, validating the JSON client-side (with a non-streaming ``messages.create``
fallback for older SDKs).

Extended thinking is configurable per the model's capabilities: ``adaptive``
(Opus 4.7+/Fable), ``off`` (models without thinking, e.g. Haiku 4.5), or
``enabled[:budget]`` (a fixed thinking budget). If the configured model rejects
the thinking parameter, it is disabled automatically for the rest of the run.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional, TypeVar

import anthropic
from pydantic import BaseModel

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

ToolExecutor = Callable[[str, dict], str]

# A thinking budget needs this much headroom under max_tokens for the answer;
# below it, thinking is skipped for that call rather than risk a 400.
_MIN_ANSWER_HEADROOM = 1024
_DEFAULT_THINKING_BUDGET = 2000

# JSON-schema keywords that Claude structured outputs does not support.
_UNSUPPORTED_KEYS = {
    "minLength",
    "maxLength",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "multipleOf",
    "minItems",
    "maxItems",
    "pattern",
    "format",
    "default",
}


def _parse_thinking(value: str | None) -> tuple[str, int]:
    """Parse the configured thinking mode into ``(mode, budget)``.

    Accepts ``adaptive`` (default), ``off``/``disabled``/``none``/``""``, or
    ``enabled``/``enabled:<budget>``.
    """
    v = (value or "").strip().lower()
    if v in ("", "off", "none", "disabled", "false", "0"):
        return "off", 0
    if v.startswith("enabled"):
        budget = _DEFAULT_THINKING_BUDGET
        if ":" in v:
            try:
                budget = int(v.split(":", 1)[1])
            except ValueError:
                pass
        return "enabled", max(_MIN_ANSWER_HEADROOM, budget)
    return "adaptive", 0


def _first_text(resp: Any) -> str:
    for block in getattr(resp, "content", []) or []:
        if getattr(block, "type", None) == "text":
            return block.text
    return ""


def _strip_unsupported(node: Any) -> Any:
    """Recursively remove unsupported keywords and tighten object schemas."""
    if isinstance(node, dict):
        cleaned = {
            k: _strip_unsupported(v) for k, v in node.items() if k not in _UNSUPPORTED_KEYS
        }
        if cleaned.get("type") == "object" and "properties" in cleaned:
            cleaned["additionalProperties"] = False
            cleaned["required"] = list(cleaned["properties"].keys())
        return cleaned
    if isinstance(node, list):
        return [_strip_unsupported(v) for v in node]
    return node


class ClaudeLLM:
    name = "claude"

    def __init__(self, api_key: str, model: str, thinking: str = "adaptive") -> None:
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._thinking_mode, self._thinking_budget = _parse_thinking(thinking)
        # Optional per-run telemetry recorder, attached by the orchestrator.
        self._recorder = None

    # --- Thinking handling -------------------------------------------------
    def _thinking_kwargs(self, max_tokens: int) -> dict:
        """Build the ``thinking`` kwarg for a call, sized against ``max_tokens``."""
        mode = self._thinking_mode
        if mode == "off":
            return {}
        if mode == "adaptive":
            return {"thinking": {"type": "adaptive"}}
        # "enabled": the budget must leave room for the answer within max_tokens.
        budget = min(self._thinking_budget, max_tokens - _MIN_ANSWER_HEADROOM)
        if budget < _MIN_ANSWER_HEADROOM:
            return {}
        return {"thinking": {"type": "enabled", "budget_tokens": budget}}

    def _note_thinking_unsupported(self, exc: Exception) -> bool:
        """Disable thinking for this instance if the model rejected it."""
        if self._thinking_mode != "off" and "thinking" in str(exc).lower():
            log.warning(
                "model %s rejected thinking (%s); disabling thinking for this run",
                self._model,
                exc,
            )
            self._thinking_mode = "off"
            return True
        return False

    def _create(self, *, max_tokens: int, **kwargs: Any) -> Any:
        """``messages.create`` with one retry that drops thinking if rejected."""
        try:
            return self._client.messages.create(
                max_tokens=max_tokens, **kwargs, **self._thinking_kwargs(max_tokens)
            )
        except anthropic.BadRequestError as exc:
            if self._note_thinking_unsupported(exc):
                return self._client.messages.create(
                    max_tokens=max_tokens, **kwargs, **self._thinking_kwargs(max_tokens)
                )
            raise

    def _stream_final(self, *, max_tokens: int, **kwargs: Any) -> Any:
        """Stream a response and return the final message, with the same retry."""
        try:
            with self._client.messages.stream(
                max_tokens=max_tokens, **kwargs, **self._thinking_kwargs(max_tokens)
            ) as stream:
                return stream.get_final_message()
        except anthropic.BadRequestError as exc:
            if self._note_thinking_unsupported(exc):
                with self._client.messages.stream(
                    max_tokens=max_tokens, **kwargs, **self._thinking_kwargs(max_tokens)
                ) as stream:
                    return stream.get_final_message()
            raise

    def _record_usage(self, resp: Any) -> None:
        """Add this response's token usage to the run's recorder, if attached."""
        rec = getattr(self, "_recorder", None)
        usage = getattr(resp, "usage", None)
        if rec is None or usage is None:
            return
        rec.record(
            getattr(usage, "input_tokens", 0) or 0,
            getattr(usage, "output_tokens", 0) or 0,
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
        # Stream the response so a generous max_tokens (room for thinking AND the
        # JSON) is safe: streaming avoids the SDK's non-streaming timeout guard and
        # request timeouts on large outputs. We use output_config.format with a
        # constraint-stripped schema and validate the JSON ourselves.
        json_schema = _strip_unsupported(schema.model_json_schema())
        common = dict(
            model=self._model,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": json_schema}},
        )
        try:
            resp = self._stream_final(max_tokens=max_tokens, **common)
        except (AttributeError, TypeError) as exc:
            log.warning(
                "messages.stream(output_config=...) unavailable (%s); using "
                "non-streaming create.",
                exc,
            )
            resp = self._create(max_tokens=max_tokens, **common)
        self._record_usage(resp)
        return self._parse_structured(resp, schema, max_tokens)

    @staticmethod
    def _parse_structured(resp: Any, schema: type[T], max_tokens: int) -> T:
        stop = getattr(resp, "stop_reason", None)
        if stop == "refusal":
            raise RuntimeError("Claude refused the request")
        text = _first_text(resp)
        if not text:
            if stop == "max_tokens":
                raise RuntimeError(
                    f"Claude reached max_tokens ({max_tokens}) before emitting any "
                    "answer — the budget was likely consumed by thinking. Increase "
                    "max_tokens for this agent."
                )
            raise RuntimeError("Claude returned no parseable structured output")
        try:
            return schema.model_validate_json(text)
        except Exception as exc:
            if stop == "max_tokens":
                raise RuntimeError(
                    f"Claude's structured output was truncated at max_tokens "
                    f"({max_tokens}). Increase max_tokens for this agent."
                ) from exc
            raise RuntimeError(
                f"Claude returned malformed structured output: {exc}"
            ) from exc

    def structured_with_tools(
        self,
        *,
        system: str,
        user: str,
        tools: list[dict],
        execute_tool: ToolExecutor,
        schema: type[T],
        mock_bootstrap: Callable[[ToolExecutor], T],  # unused for the real model
        max_tokens: int = 4000,
        max_steps: int = 3,
    ) -> T:
        """Drive an agentic tool-use loop, returning schema-constrained output.

        Two phases. First a tool-use loop offering ``tools`` with **no** output
        format — passing ``output_config.format`` alongside tools makes the
        model short-circuit straight to JSON instead of calling the tools. Once
        the model stops calling tools (or the step budget is hit), a final call
        with ``output_config.format`` and no tools extracts the structured
        answer from the gathered context.
        """
        messages: list[dict] = [{"role": "user", "content": user}]

        # --- Phase 1: tool-use loop ---------------------------------------
        for _ in range(max_steps):
            resp = self._create(
                model=self._model,
                max_tokens=max_tokens,
                system=system,
                messages=messages,
                tools=tools,
            )
            self._record_usage(resp)
            if getattr(resp, "stop_reason", None) == "refusal":
                raise RuntimeError("Claude refused the request")

            tool_uses = [
                b for b in (resp.content or []) if getattr(b, "type", None) == "tool_use"
            ]
            messages.append({"role": "assistant", "content": resp.content})
            if not tool_uses:
                break

            results = []
            for tu in tool_uses:
                try:
                    output = execute_tool(tu.name, dict(tu.input or {}))
                except Exception as exc:  # surface the failure to the model
                    output = f"Tool '{tu.name}' failed: {exc}"
                results.append(
                    {"type": "tool_result", "tool_use_id": tu.id, "content": output}
                )
            messages.append({"role": "user", "content": results})

        # --- Phase 2: force the structured answer (no tools) --------------
        json_schema = _strip_unsupported(schema.model_json_schema())
        messages.append(
            {
                "role": "user",
                "content": "Now return your final selection as structured output.",
            }
        )
        resp = self._create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
            output_config={"format": {"type": "json_schema", "schema": json_schema}},
        )
        self._record_usage(resp)
        if getattr(resp, "stop_reason", None) == "refusal":
            raise RuntimeError("Claude refused the request")
        text = _first_text(resp)
        if not text:
            raise RuntimeError("Claude returned no parseable structured output")
        return schema.model_validate_json(text)
