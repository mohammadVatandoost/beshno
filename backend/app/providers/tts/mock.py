"""Mock TTS provider — produces a silent WAV sized to the dialogue length.

Yields a real, playable audio file (silence) so the player and duration logic
work end-to-end without any TTS credentials.
"""

from __future__ import annotations

from .base import SpeechSegment, SynthesisResult
from .wavutil import duration_of, silence_pcm, write_wav

_SAMPLE_RATE = 24000
_SECONDS_PER_CHAR = 0.06
_TURN_GAP_SECONDS = 0.35


class MockTTS:
    name = "mock"

    def synthesize(
        self, segments: list[SpeechSegment], *, out_path: str
    ) -> SynthesisResult:
        pcm_chunks: list[bytes] = []
        for seg in segments:
            spoken = max(0.8, min(25.0, len(seg.text) * _SECONDS_PER_CHAR))
            pcm_chunks.append(silence_pcm(spoken, _SAMPLE_RATE))
            pcm_chunks.append(silence_pcm(_TURN_GAP_SECONDS, _SAMPLE_RATE))

        write_wav(out_path, pcm_chunks, _SAMPLE_RATE)
        return SynthesisResult(
            path=out_path,
            format="wav",
            duration_seconds=duration_of(pcm_chunks, _SAMPLE_RATE),
        )
