"""Claude (Anthropic) LLM provider using structured outputs.

Primary path uses ``messages.parse`` with a Pydantic ``output_format`` (the SDK
strips JSON-schema constraints Claude doesn't support and validates the result
client-side). If the installed SDK predates that helper, we fall back to
``messages.create`` with ``output_config.format`` and validate manually.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional, TypeVar

import anthropic
from pydantic import BaseModel

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

ToolExecutor = Callable[[str, dict], str]

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

    def __init__(self, api_key: str, model: str) -> None:
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def structured(
        self,
        *,
        system: str,
        user: str,
        schema: type[T],
        mock_example: Optional[T] = None,
        max_tokens: int = 8000,
    ) -> T:
        try:
            resp = self._client.messages.parse(
                model=self._model,
                max_tokens=max_tokens,
                thinking={"type": "adaptive"},
                system=system,
                messages=[{"role": "user", "content": user}],
                output_format=schema,
            )
            if getattr(resp, "stop_reason", None) == "refusal":
                raise RuntimeError("Claude refused the request")
            parsed = getattr(resp, "parsed_output", None)
            if parsed is not None:
                return parsed
            text = _first_text(resp)
            if text:
                return schema.model_validate_json(text)
            raise RuntimeError("Claude returned no parseable structured output")
        except (AttributeError, TypeError) as exc:
            log.warning(
                "messages.parse unavailable (%s); falling back to output_config.format",
                exc,
            )
            return self._structured_fallback(
                system=system, user=user, schema=schema, max_tokens=max_tokens
            )

    def _structured_fallback(
        self, *, system: str, user: str, schema: type[T], max_tokens: int
    ) -> T:
        json_schema = _strip_unsupported(schema.model_json_schema())
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            thinking={"type": "adaptive"},
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": json_schema}},
        )
        if getattr(resp, "stop_reason", None) == "refusal":
            raise RuntimeError("Claude refused the request")
        text = _first_text(resp)
        if not text:
            raise RuntimeError("Claude returned no text content")
        return schema.model_validate_json(text)

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
            resp = self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                thinking={"type": "adaptive"},
                system=system,
                messages=messages,
                tools=tools,
            )
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
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            thinking={"type": "adaptive"},
            system=system,
            messages=messages,
            output_config={"format": {"type": "json_schema", "schema": json_schema}},
        )
        if getattr(resp, "stop_reason", None) == "refusal":
            raise RuntimeError("Claude refused the request")
        text = _first_text(resp)
        if not text:
            raise RuntimeError("Claude returned no parseable structured output")
        return schema.model_validate_json(text)
