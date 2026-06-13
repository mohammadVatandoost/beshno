"""Search provider protocol and the raw result shape."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class RawSearchResult:
    title: str
    url: str
    content: str
    score: float = 0.0


class SearchProvider(Protocol):
    name: str

    def search(
        self, query: str, *, language: str, max_results: int = 10
    ) -> list[RawSearchResult]:
        ...
