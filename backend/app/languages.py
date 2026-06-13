"""Language helpers: a curated list for the UI and BCP-47 mapping for TTS."""

from __future__ import annotations

# Languages offered in the frontend dropdowns.
COMMON_LANGUAGES: list[str] = [
    "English",
    "Spanish",
    "French",
    "German",
    "Italian",
    "Portuguese",
    "Dutch",
    "Russian",
    "Japanese",
    "Chinese",
    "Korean",
    "Arabic",
    "Hindi",
    "Turkish",
    "Persian",
    "Polish",
    "Swedish",
    "Greek",
    "Hebrew",
    "Vietnamese",
]

# Map a language name to a BCP-47 locale usable by Google Cloud TTS.
_LANGUAGE_TO_BCP47: dict[str, str] = {
    "english": "en-US",
    "spanish": "es-ES",
    "french": "fr-FR",
    "german": "de-DE",
    "italian": "it-IT",
    "portuguese": "pt-BR",
    "dutch": "nl-NL",
    "russian": "ru-RU",
    "japanese": "ja-JP",
    "chinese": "cmn-CN",
    "mandarin": "cmn-CN",
    "korean": "ko-KR",
    "arabic": "ar-XA",
    "hindi": "hi-IN",
    "turkish": "tr-TR",
    "persian": "fa-IR",
    "farsi": "fa-IR",
    "polish": "pl-PL",
    "swedish": "sv-SE",
    "greek": "el-GR",
    "hebrew": "he-IL",
    "vietnamese": "vi-VN",
}


def to_bcp47(language_name: str, default: str = "en-US") -> str:
    """Best-effort map of a free-text language name to a BCP-47 locale."""
    return _LANGUAGE_TO_BCP47.get((language_name or "").strip().lower(), default)
