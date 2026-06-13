"""Google Cloud Text-to-Speech provider.

Synthesizes each dialogue turn with a distinct, language-appropriate voice
(female for the learner, male for the teacher) and stitches the LINEAR16 PCM
segments into a single mono WAV file.
"""

from __future__ import annotations

import logging

from .base import SpeechSegment, SynthesisResult
from .wavutil import duration_of, pcm_from_audio, silence_pcm, write_wav

log = logging.getLogger(__name__)

_SAMPLE_RATE = 24000
_TURN_GAP_SECONDS = 0.45


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
            pcm_chunks.append(silence_pcm(_TURN_GAP_SECONDS, _SAMPLE_RATE))

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
