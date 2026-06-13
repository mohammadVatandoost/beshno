"""Agent 1 — Search Filter.

Analyzes raw search results and selects the top 5 most relevant, reliable
resources for the topic and language pair.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..content_models import Source
from ..providers.search.base import RawSearchResult
from .base import Agent

SYSTEM_PROMPT = """\
You are Agent 1, the Search Filter, in a language-learning podcast pipeline.

You are given a list of raw web search results for a topic. Select the 5 most
relevant and reliable resources for building a learning podcast about the topic
in the target language.

Selection criteria, in order:
1. Relevance to the exact topic.
2. Reliability and neutrality of the source (prefer encyclopedic, educational,
   reputable news over low-quality or promotional pages).
3. Substance: the page must contain enough explanatory content to summarize.
4. Diversity: prefer a mix of angles (overview, history/culture, everyday use).

Return at most 5 sources. For each, give a relevance_score between 0 and 1 and
a one-sentence reason. Do not invent URLs — only choose from the provided list.
"""


class SearchFilterResult(BaseModel):
    selected: list[Source] = Field(default_factory=list)


class SearchFilterAgent(Agent):
    name = "search_filter"

    def run(
        self,
        *,
        topic: str,
        target_language: str,
        native_language: str,
        cefr_level: str,
        results: list[RawSearchResult],
    ) -> SearchFilterResult:
        listing = "\n\n".join(
            f"[{i}] {r.title}\n"
            f"URL: {r.url}\n"
            f"Search score: {r.score}\n"
            f"Excerpt: {r.content[:800]}"
            for i, r in enumerate(results)
        )
        user = (
            f"Topic: {topic}\n"
            f"Target (learning) language: {target_language}\n"
            f"Learner's native language: {native_language}\n"
            f"Learner CEFR level: {cefr_level}\n\n"
            f"Raw search results:\n{listing}\n\n"
            f"Select the top 5 sources."
        )

        mock = SearchFilterResult(
            selected=[
                Source(
                    title=r.title or r.url,
                    url=r.url,
                    relevance_score=min(max(r.score or 0.85, 0.0), 1.0),
                    reason=f"Clear, reliable overview suitable for a {cefr_level} learner.",
                )
                for r in results[:5]
            ]
        )

        return self.llm.structured(
            system=SYSTEM_PROMPT,
            user=user,
            schema=SearchFilterResult,
            mock_example=mock,
            max_tokens=4000,
        )
