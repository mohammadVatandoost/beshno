"""TTS provider protocol and shared dataclasses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol


@dataclass
class SpeechSegment:
    text: str
    language_code: str  # BCP-47, e.g. "en-US"
    gender: Literal["female", "male"]
    # Silence (seconds) to append after this segment. None -> provider default.
    # Small values make a sequence play near-seamlessly; larger values add pauses.
    pause_after: float | None = None


@dataclass
class SynthesisResult:
    path: str
    format: str  # e.g. "wav"
    duration_seconds: float


class TTSProvider(Protocol):
    name: str

    def synthesize(
        self, segments: list[SpeechSegment], *, out_path: str
    ) -> SynthesisResult:
        ...
