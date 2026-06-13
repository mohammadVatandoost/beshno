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

    def __init__(self) -> None:
        # Imported lazily so the package isn't a hard dependency for mock runs.
        from google.cloud import texttospeech

        self._tts = texttospeech
        self._client = texttospeech.TextToSpeechClient()

    def synthesize(
        self, segments: list[SpeechSegment], *, out_path: str
    ) -> SynthesisResult:
        tts = self._tts
        pcm_chunks: list[bytes] = []

        for seg in segments:
            if not seg.text.strip():
                continue
            synthesis_input = tts.SynthesisInput(text=seg.text)
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
            response = self._client.synthesize_speech(
                input=synthesis_input, voice=voice, audio_config=audio_config
            )
            pcm_chunks.append(pcm_from_audio(response.audio_content))
            pcm_chunks.append(silence_pcm(_TURN_GAP_SECONDS, _SAMPLE_RATE))

        write_wav(out_path, pcm_chunks, _SAMPLE_RATE)
        duration = duration_of(pcm_chunks, _SAMPLE_RATE)
        log.info("Google TTS wrote %s (%.1fs)", out_path, duration)
        return SynthesisResult(path=out_path, format="wav", duration_seconds=duration)
