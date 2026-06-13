"""Local filesystem storage for generated audio files."""

from __future__ import annotations

import os

from .config import get_settings


class Storage:
    def __init__(self, base_dir: str | None = None) -> None:
        self.base_dir = base_dir or get_settings().storage_dir
        self.audio_dir = os.path.join(self.base_dir, "audio")

    def ensure(self) -> None:
        os.makedirs(self.audio_dir, exist_ok=True)

    def audio_path(self, podcast_id: str, ext: str = "wav") -> str:
        return os.path.join(self.audio_dir, f"{podcast_id}.{ext}")
