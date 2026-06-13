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
import time

from .base import SegmentTiming, SpeechSegment, SynthesisResult
from .wavutil import bytes_to_seconds, duration_of, pcm_from_audio, silence_pcm, write_wav

log = logging.getLogger(__name__)

_SAMPLE_RATE = 24000
_TURN_GAP_SECONDS = 0.45

# Transient-error retry. Google TTS occasionally returns 503/500/timeout; a
# single blip should not abort the whole podcast, so retry with backoff.
_MAX_RETRIES = 4
_RETRY_BASE_DELAY = 1.0  # seconds; doubles each attempt
_RETRY_MAX_DELAY = 12.0

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

        # Predicate that recognizes retryable (transient) API errors —
        # ServiceUnavailable (503), InternalServerError (500), TooManyRequests
        # (429), DeadlineExceeded, etc.
        try:
            from google.api_core import retry as garetry

            self._is_transient = garetry.if_transient_error
        except Exception:  # pragma: no cover - defensive
            self._is_transient = lambda exc: False  # noqa: E731

        self._tts = texttospeech
        if api_key:
            # API-key auth — no service-account JSON required.
            self._client = texttospeech.TextToSpeechClient(
                client_options={"api_key": api_key}
            )
        else:
            # Application Default Credentials (GOOGLE_APPLICATION_CREDENTIALS, etc.).
            self._client = texttospeech.TextToSpeechClient()

        # Caches so the catalogue is fetched at most once per language and a
        # voice is resolved at most once per (language, gender).
        self._voices_by_lang: dict[str, list] = {}
        self._voice_cache: dict[str, object] = {}

    def _list_voices(self, language_code: str) -> list:
        """Available voices for a language, cached. Empty list on failure."""
        if language_code not in self._voices_by_lang:
            resp = self._client.list_voices(language_code=language_code)
            self._voices_by_lang[language_code] = list(resp.voices)
        return self._voices_by_lang[language_code]

    def _pick_voice(self, tts, language_code: str, gender: str):
        """Best-tier voice for (language, gender), with graceful fallback.

        Prefers Chirp 3: HD -> Neural2 -> WaveNet -> Standard. If discovery
        fails or nothing matches, returns a gender-only selection and lets the
        API pick its default voice for the language.
        """
        key = f"{language_code}:{gender}"
        if key in self._voice_cache:
            return self._voice_cache[key]

        target_gender = (
            tts.SsmlVoiceGender.FEMALE
            if gender == "female"
            else tts.SsmlVoiceGender.MALE
        )
        chosen_name: str | None = None
        try:
            candidates = [
                v
                for v in self._list_voices(language_code)
                if language_code in v.language_codes
                and v.ssml_gender == target_gender
            ]
            if candidates:
                # Highest tier wins; voice name breaks ties deterministically.
                best = max(candidates, key=lambda v: (_tier_rank(v.name), v.name))
                chosen_name = best.name
        except Exception as exc:  # noqa: BLE001 - discovery is best-effort
            log.warning(
                "GoogleTTS: voice discovery failed for %s/%s (%s); "
                "falling back to API default voice.",
                language_code,
                gender,
                exc,
            )

        if chosen_name:
            voice = tts.VoiceSelectionParams(
                language_code=language_code,
                name=chosen_name,
                ssml_gender=target_gender,
            )
            log.info(
                "GoogleTTS: selected voice %s (tier=%d) for %s/%s",
                chosen_name,
                _tier_rank(chosen_name),
                language_code,
                gender,
            )
        else:
            voice = tts.VoiceSelectionParams(
                language_code=language_code, ssml_gender=target_gender
            )
            log.info(
                "GoogleTTS: no named voice for %s/%s; using API default.",
                language_code,
                gender,
            )

        self._voice_cache[key] = voice
        return voice

    def _synthesize_speech(self, *, input, voice, audio_config):
        """Call the API, retrying transient failures with exponential backoff."""
        delay = _RETRY_BASE_DELAY
        for attempt in range(_MAX_RETRIES + 1):
            try:
                return self._client.synthesize_speech(
                    input=input, voice=voice, audio_config=audio_config
                )
            except Exception as exc:  # noqa: BLE001 - inspected below
                transient = False
                try:
                    transient = bool(self._is_transient(exc))
                except Exception:  # pragma: no cover - predicate is defensive
                    transient = False
                if not transient or attempt >= _MAX_RETRIES:
                    raise
                log.warning(
                    "GoogleTTS: transient error (%s); retrying in %.1fs "
                    "(attempt %d/%d)",
                    exc,
                    delay,
                    attempt + 1,
                    _MAX_RETRIES,
                )
                time.sleep(delay)
                delay = min(delay * 2, _RETRY_MAX_DELAY)

    def synthesize(
        self, segments: list[SpeechSegment], *, out_path: str
    ) -> SynthesisResult:
        tts = self._tts
        pcm_chunks: list[bytes] = []
        timings: list[SegmentTiming] = []
        cursor_bytes = 0
        total_audio_bytes = 0
        spoken_segments = 0

        log.info("GoogleTTS: synthesizing %d segment(s) -> %s", len(segments), out_path)
        for i, seg in enumerate(segments):
            if not seg.text.strip():
                log.debug("GoogleTTS: skipping empty segment %d", i)
                # Keep timings aligned 1:1 with the input: zero-length here.
                here = bytes_to_seconds(cursor_bytes, _SAMPLE_RATE)
                timings.append(SegmentTiming(start=here, end=here))
                continue
            voice = self._pick_voice(tts, seg.language_code, seg.gender)
            audio_config = tts.AudioConfig(
                audio_encoding=tts.AudioEncoding.LINEAR16,
                sample_rate_hertz=_SAMPLE_RATE,
            )
            try:
                response = self._synthesize_speech(
                    input=tts.SynthesisInput(text=seg.text),
                    voice=voice,
                    audio_config=audio_config,
                )
            except Exception as exc:
                log.error(
                    "GoogleTTS: synthesis failed on segment %d (lang=%s, gender=%s) "
                    "after %d retr%s: %s",
                    i,
                    seg.language_code,
                    seg.gender,
                    _MAX_RETRIES,
                    "y" if _MAX_RETRIES == 1 else "ies",
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
            start = bytes_to_seconds(cursor_bytes, _SAMPLE_RATE)
            pcm_chunks.append(pcm)
            cursor_bytes += len(pcm)
            timings.append(
                SegmentTiming(start=start, end=bytes_to_seconds(cursor_bytes, _SAMPLE_RATE))
            )
            gap = seg.pause_after if seg.pause_after is not None else _TURN_GAP_SECONDS
            gap_pcm = silence_pcm(gap, _SAMPLE_RATE)
            pcm_chunks.append(gap_pcm)
            cursor_bytes += len(gap_pcm)

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
        return SynthesisResult(
            path=out_path, format="wav", duration_seconds=duration, timings=timings
        )
