"""Mock search provider — deterministic canned results, no network needed."""

from __future__ import annotations

from .base import RawSearchResult


class MockSearch:
    name = "mock"

    def search(
        self, query: str, *, language: str, max_results: int = 10
    ) -> list[RawSearchResult]:
        topic = query.strip() or "the topic"
        templates = [
            (
                f"An introduction to {topic}",
                "encyclopedia.example.org",
                f"{topic.capitalize()} is a subject that spans history, culture and "
                f"everyday life. This overview explains the core ideas behind {topic}, "
                f"how it developed over time, and why it matters to ordinary people. "
                f"It covers key terms, common misconceptions, and a few memorable facts "
                f"that make {topic} approachable for newcomers.",
            ),
            (
                f"{topic.capitalize()}: a short explainer",
                "news.example.com",
                f"Recent coverage of {topic} highlights how it affects daily routines. "
                f"Experts describe simple cause-and-effect relationships and offer "
                f"practical examples. The piece uses clear, accessible language and "
                f"avoids heavy jargon, making it suitable for learners.",
            ),
            (
                f"Everyday {topic} for beginners",
                "learn.example.net",
                f"A beginner-friendly guide to {topic}. It breaks the subject into small "
                f"steps, defines important vocabulary, and uses everyday situations to "
                f"illustrate each point. Short sentences and concrete examples keep the "
                f"explanation easy to follow.",
            ),
            (
                f"Five facts about {topic}",
                "facts.example.io",
                f"This article lists five surprising and verifiable facts about {topic}. "
                f"Each fact is explained with a brief, plain-language note so readers can "
                f"understand the context without prior knowledge.",
            ),
            (
                f"The culture and history of {topic}",
                "culture.example.org",
                f"A look at the cultural and historical background of {topic}. The text "
                f"connects past events to present-day understanding and points out idioms "
                f"and expressions associated with {topic}.",
            ),
            (
                f"Common questions about {topic}",
                "qa.example.com",
                f"A frequently-asked-questions style overview of {topic}, answering the "
                f"questions newcomers most often ask, with concise, factual responses.",
            ),
        ]
        results: list[RawSearchResult] = []
        for i, (title, host, content) in enumerate(templates[:max_results]):
            results.append(
                RawSearchResult(
                    title=title,
                    url=f"https://{host}/{topic.lower().replace(' ', '-')}",
                    content=content,
                    score=round(0.95 - i * 0.07, 2),
                )
            )
        return results
