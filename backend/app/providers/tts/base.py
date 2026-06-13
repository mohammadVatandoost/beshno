"""TTS provider protocol and shared dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional, Protocol


@dataclass
class SpeechSegment:
    text: str
    language_code: str  # BCP-47, e.g. "en-US"
    gender: Literal["female", "male"]
    # Silence (seconds) to append after this segment. None -> provider default.
    # Small values make a sequence play near-seamlessly; larger values add pauses.
    pause_after: float | None = None
    # Optional descriptor carried through to the timed transcript (kind, phase,
    # group, lang, …) so the synthesized timing can be mapped back to the text.
    cue: Optional[dict[str, Any]] = None


@dataclass
class SegmentTiming:
    """Where a segment's *speech* sits in the final track (seconds)."""

    start: float
    end: float


@dataclass
class SynthesisResult:
    path: str
    format: str  # e.g. "wav"
    duration_seconds: float
    # One entry per input segment, aligned by index: the [start, end) of that
    # segment's speech in the output (excluding the trailing pause). Empty if the
    # provider doesn't report timing.
    timings: list[SegmentTiming] = field(default_factory=list)


class TTSProvider(Protocol):
    name: str

    def synthesize(
        self, segments: list[SpeechSegment], *, out_path: str
    ) -> SynthesisResult:
        ...
