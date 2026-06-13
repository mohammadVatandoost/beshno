"""Helpers to stitch PCM segments into a single mono 16-bit WAV file."""

from __future__ import annotations

import io
import wave

SAMPLE_RATE = 24000
SAMPLE_WIDTH = 2  # 16-bit
CHANNELS = 1


def pcm_from_audio(data: bytes) -> bytes:
    """Extract raw PCM frames from WAV bytes, or pass through raw PCM."""
    try:
        with wave.open(io.BytesIO(data), "rb") as w:
            return w.readframes(w.getnframes())
    except (wave.Error, EOFError):
        return data  # assume already headerless PCM


def silence_pcm(seconds: float, sample_rate: int = SAMPLE_RATE) -> bytes:
    frames = int(max(0.0, seconds) * sample_rate)
    return b"\x00\x00" * frames


def bytes_to_seconds(num_bytes: int, sample_rate: int = SAMPLE_RATE) -> float:
    """Seconds of audio represented by ``num_bytes`` of mono 16-bit PCM."""
    return num_bytes / float(SAMPLE_WIDTH * CHANNELS * sample_rate)


def duration_of(pcm_chunks: list[bytes], sample_rate: int = SAMPLE_RATE) -> float:
    total_bytes = sum(len(c) for c in pcm_chunks)
    return bytes_to_seconds(total_bytes, sample_rate)


def write_wav(path: str, pcm_chunks: list[bytes], sample_rate: int = SAMPLE_RATE) -> None:
    with wave.open(path, "wb") as w:
        w.setnchannels(CHANNELS)
        w.setsampwidth(SAMPLE_WIDTH)
        w.setframerate(sample_rate)
        for chunk in pcm_chunks:
            w.writeframes(chunk)
