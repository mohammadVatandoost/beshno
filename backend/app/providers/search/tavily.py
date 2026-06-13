"""Tavily search provider (https://tavily.com)."""

from __future__ import annotations

import logging

import httpx

from .base import RawSearchResult

log = logging.getLogger(__name__)

_ENDPOINT = "https://api.tavily.com/search"


class TavilySearch:
    name = "tavily"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def search(
        self, query: str, *, language: str, max_results: int = 10
    ) -> list[RawSearchResult]:
        payload = {
            "api_key": self._api_key,  # legacy auth (still accepted)
            "query": query,
            "search_depth": "advanced",
            "max_results": max_results,
            "include_raw_content": True,
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(_ENDPOINT, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        results: list[RawSearchResult] = []
        for item in data.get("results", []):
            content = item.get("raw_content") or item.get("content") or ""
            results.append(
                RawSearchResult(
                    title=item.get("title", "") or item.get("url", ""),
                    url=item.get("url", ""),
                    content=content,
                    score=float(item.get("score") or 0.0),
                )
            )
        log.info("Tavily returned %d results for %r", len(results), query)
        return results
