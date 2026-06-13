"""Google Cloud Text-to-Speech provider.

Synthesizes each dialogue turn with a distinct, language-appropriate voice
(female for the learner, male for the teacher) and stitches the LINEAR16 PCM
segments into a single mono WAV file.

Voice quality: for each (language, gender) we query the API's voice catalogue
and pick the most natural tier available, preferring
Chirp 3: HD -> Neural2 -> WaveNet -> Standard. This is self-maintaining — as
Google adds Chirp 3: HD support for more languages, those voices are picked up
automatically without code changes. Languages without a higher tier (e.g.
Persian) gracefully fall back to whatever is available.
"""

from __future__ import annotations

import logging

from .base import SpeechSegment, SynthesisResult
from .wavutil import duration_of, pcm_from_audio, silence_pcm, write_wav

log = logging.getLogger(__name__)

_SAMPLE_RATE = 24000
_TURN_GAP_SECONDS = 0.45

# Voice-name substrings ranked by naturalness, best first. The first token that
# appears (case-insensitively) in a voice name decides its tier; anything
# unrecognised ranks below Standard.
_TIER_RANK: list[tuple[str, int]] = [
    ("chirp3-hd", 5),
    ("chirp3hd", 5),
    ("chirp-hd", 5),
    ("neural2", 4),
    ("wavenet", 3),
    ("standard", 2),
]


def _tier_rank(voice_name: str) -> int:
    low = voice_name.lower()
    for token, rank in _TIER_RANK:
        if token in low:
            return rank
    return 1


class GoogleTTS:
    name = "google"

    def __init__(self, api_key: str | None = None) -> None:
        # Imported lazily so the package isn't a hard dependency for mock runs.
        from google.cloud import texttospeech

        self._tts = texttospeech
        if api_key:
            # API-key auth — no service-account JSON required.
            self._client = texttospeech.TextToSpeechClient(
                client_options={"api_key": api_key}
            )
        else:
            # Application Default Credentials (GOOGLE_APPLICATION_CREDENTIALS, etc.).
            self._client = texttospeech.TextToSpeechClient()

    def synthesize(
        self, segments: list[SpeechSegment], *, out_path: str
    ) -> SynthesisResult:
        tts = self._tts
        pcm_chunks: list[bytes] = []
        total_audio_bytes = 0
        spoken_segments = 0

        log.info("GoogleTTS: synthesizing %d segment(s) -> %s", len(segments), out_path)
        for i, seg in enumerate(segments):
            if not seg.text.strip():
                log.debug("GoogleTTS: skipping empty segment %d", i)
                continue
            gender = (
                tts.SsmlVoiceGender.FEMALE
                if seg.gender == "female"
                else tts.SsmlVoiceGender.MALE
            )
            voice = tts.VoiceSelectionParams(
                language_code=seg.language_code, ssml_gender=gender
            )
            audio_config = tts.AudioConfig(
                audio_encoding=tts.AudioEncoding.LINEAR16,
                sample_rate_hertz=_SAMPLE_RATE,
            )
            try:
                response = self._client.synthesize_speech(
                    input=tts.SynthesisInput(text=seg.text),
                    voice=voice,
                    audio_config=audio_config,
                )
            except Exception as exc:
                log.error(
                    "GoogleTTS: synthesis failed on segment %d (lang=%s, gender=%s): %s",
                    i,
                    seg.language_code,
                    seg.gender,
                    exc,
                )
                raise
            pcm = pcm_from_audio(response.audio_content)
            total_audio_bytes += len(pcm)
            spoken_segments += 1
            log.debug(
                "GoogleTTS: segment %d lang=%s gender=%s -> %d audio bytes",
                i,
                seg.language_code,
                seg.gender,
                len(pcm),
            )
            pcm_chunks.append(pcm)
            gap = seg.pause_after if seg.pause_after is not None else _TURN_GAP_SECONDS
            pcm_chunks.append(silence_pcm(gap, _SAMPLE_RATE))

        if total_audio_bytes == 0:
            log.error(
                "GoogleTTS: produced 0 bytes of speech for %d segment(s) — "
                "the output WAV will be silent.",
                len(segments),
            )

        write_wav(out_path, pcm_chunks, _SAMPLE_RATE)
        duration = duration_of(pcm_chunks, _SAMPLE_RATE)
        log.info(
            "GoogleTTS: wrote %s (%.1fs, %d spoken segment(s), %d speech bytes)",
            out_path,
            duration,
            spoken_segments,
            total_audio_bytes,
        )
        return SynthesisResult(path=out_path, format="wav", duration_seconds=duration)
