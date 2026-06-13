"""Mock TTS provider — produces a silent WAV sized to the dialogue length.

Yields a real, playable audio file (silence) so the player and duration logic
work end-to-end without any TTS credentials.
"""

from __future__ import annotations

import logging

from .base import SegmentTiming, SpeechSegment, SynthesisResult
from .wavutil import bytes_to_seconds, duration_of, silence_pcm, write_wav

log = logging.getLogger(__name__)

_SAMPLE_RATE = 24000
_SECONDS_PER_CHAR = 0.06
_TURN_GAP_SECONDS = 0.35


class MockTTS:
    name = "mock"

    def synthesize(
        self, segments: list[SpeechSegment], *, out_path: str
    ) -> SynthesisResult:
        pcm_chunks: list[bytes] = []
        timings: list[SegmentTiming] = []
        cursor_bytes = 0
        for seg in segments:
            spoken = max(0.8, min(25.0, len(seg.text) * _SECONDS_PER_CHAR))
            speech = silence_pcm(spoken, _SAMPLE_RATE)
            start = bytes_to_seconds(cursor_bytes, _SAMPLE_RATE)
            pcm_chunks.append(speech)
            cursor_bytes += len(speech)
            timings.append(
                SegmentTiming(start=start, end=bytes_to_seconds(cursor_bytes, _SAMPLE_RATE))
            )
            gap = seg.pause_after if seg.pause_after is not None else _TURN_GAP_SECONDS
            gap_pcm = silence_pcm(gap, _SAMPLE_RATE)
            pcm_chunks.append(gap_pcm)
            cursor_bytes += len(gap_pcm)

        write_wav(out_path, pcm_chunks, _SAMPLE_RATE)
        duration = duration_of(pcm_chunks, _SAMPLE_RATE)
        log.warning(
            "MockTTS: wrote SILENT placeholder audio %s (%.1fs, %d segments). "
            "This file has a duration but NO sound. Set GOOGLE_API_KEY or "
            "GOOGLE_APPLICATION_CREDENTIALS for real speech.",
            out_path,
            duration,
            len(segments),
        )
        return SynthesisResult(
            path=out_path, format="wav", duration_seconds=duration, timings=timings
        )
