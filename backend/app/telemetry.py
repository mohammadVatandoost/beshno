"""LLM usage telemetry — token accounting and cost estimation.

A :class:`TelemetryRecorder` is attached to a pipeline run's LLM instance; every
model call adds its token usage to it. Because ``get_llm()`` returns a fresh
provider per run, each concurrent generation gets its own recorder — counters
are never shared across runs. The recorder is thread-safe so the parallel
exercise step (which runs on a worker thread but shares the run's LLM instance)
records its usage safely alongside the rest of the pipeline.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass

# Price per 1M tokens (input, output) in USD, keyed by model id. Used only for a
# rough cost estimate shown in the UI — keep roughly in sync with list pricing.
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "claude-fable-5": (10.0, 50.0),
    "claude-opus-4-8": (5.0, 25.0),
    "claude-opus-4-7": (5.0, 25.0),
    "claude-opus-4-6": (5.0, 25.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
}
# Human-friendly names for the pricing footnote shown in the UI.
MODEL_DISPLAY_NAMES: dict[str, str] = {
    "claude-fable-5": "Fable 5",
    "claude-opus-4-8": "Opus 4.8",
    "claude-opus-4-7": "Opus 4.7",
    "claude-opus-4-6": "Opus 4.6",
    "claude-sonnet-4-6": "Sonnet 4.6",
    "claude-haiku-4-5": "Haiku 4.5",
}
DEFAULT_PRICING_MODEL = "claude-opus-4-8"

# Matches a trailing dated snapshot suffix, e.g. the "-20251001" in
# "claude-haiku-4-5-20251001", so concrete model ids resolve to a pricing key.
_DATE_SUFFIX = re.compile(r"-\d{8}$")


def normalize_pricing_model(model: str) -> str:
    """Resolve a concrete model id to a key in :data:`MODEL_PRICING`.

    Strips a trailing ``-YYYYMMDD`` snapshot suffix (e.g.
    ``claude-haiku-4-5-20251001`` -> ``claude-haiku-4-5``). Falls back to
    :data:`DEFAULT_PRICING_MODEL` when the model is unknown.
    """
    if model in MODEL_PRICING:
        return model
    base = _DATE_SUFFIX.sub("", model or "")
    return base if base in MODEL_PRICING else DEFAULT_PRICING_MODEL


def pricing_label(model: str) -> str:
    """Friendly name of the model whose list price is used for the estimate."""
    key = normalize_pricing_model(model)
    return MODEL_DISPLAY_NAMES.get(key, key)


@dataclass(frozen=True)
class UsageSnapshot:
    """An immutable view of a recorder's running totals."""

    input_tokens: int
    output_tokens: int
    calls: int


class TelemetryRecorder:
    """Thread-safe accumulator of LLM token usage for one pipeline run."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._input = 0
        self._output = 0
        self._calls = 0

    def record(self, input_tokens: int, output_tokens: int) -> None:
        """Add one model call's token usage."""
        with self._lock:
            self._input += max(0, int(input_tokens or 0))
            self._output += max(0, int(output_tokens or 0))
            self._calls += 1

    def snapshot(self) -> UsageSnapshot:
        """Current cumulative totals (used to diff per-step usage)."""
        with self._lock:
            return UsageSnapshot(self._input, self._output, self._calls)


def estimate_cost(
    input_tokens: int, output_tokens: int, model: str = DEFAULT_PRICING_MODEL
) -> float:
    """Rough USD cost for the given token counts at ``model``'s list price."""
    in_price, out_price = MODEL_PRICING[normalize_pricing_model(model)]
    cost = (input_tokens / 1_000_000) * in_price
    cost += (output_tokens / 1_000_000) * out_price
    return round(cost, 6)
