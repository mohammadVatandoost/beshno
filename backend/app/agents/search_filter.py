"""Agent 1 — Search Filter.

Researches a topic *agentically*: instead of receiving a pre-fetched batch of
results as context, the agent calls the topic-retrieval MCP tool itself (and may
refine its query across several calls), then selects the 5 most relevant,
reliable resources for the topic and language pair.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field

from ..config import get_settings
from ..content_models import Source
from ..mcp import TopicRetrievalMCP
from .base import Agent

SYSTEM_PROMPT = """\
You are Agent 1, the Search Filter, in a language-learning podcast pipeline.

You MUST use the `search_topic` tool to research the topic on the web before
selecting anything — never rely on prior knowledge or invent URLs. Call it at
least once, and feel free to call it again with refined or alternative queries
to surface a diverse, reliable set of sources (overview, history/culture,
everyday use). Then select the 5 most relevant and reliable resources for
building a learning podcast about the topic in the target language.

Selection criteria, in order:
1. Relevance to the exact topic.
2. Reliability and neutrality of the source (prefer encyclopedic, educational,
   reputable news over low-quality or promotional pages).
3. Substance: the page must contain enough explanatory content to summarize.
4. Diversity: prefer a mix of angles (overview, history/culture, everyday use).

Return at most 5 sources. For each, give a relevance_score between 0 and 1 and
a one-sentence reason. Only choose from URLs returned by `search_topic` — never
invent URLs.
"""


class SearchFilterResult(BaseModel):
    selected: list[Source] = Field(default_factory=list)


@dataclass
class RetrievalOutcome:
    """What the agentic retrieval+filter stage produced."""

    selection: SearchFilterResult
    materials: str
    retrieved_count: int = 0


class SearchFilterAgent(Agent):
    name = "search_filter"

    def run(
        self,
        *,
        topic: str,
        target_language: str,
        native_language: str,
        cefr_level: str,
    ) -> RetrievalOutcome:
        settings = get_settings()
        max_results = settings.search_max_results

        user = (
            f"Topic: {topic}\n"
            f"Target (learning) language: {target_language}\n"
            f"Learner's native language: {native_language}\n"
            f"Learner CEFR level: {cefr_level}\n\n"
            f"Research this topic with the search_topic tool, then select the top "
            f"5 sources."
        )

        with TopicRetrievalMCP() as mcp:
            def seed_selection(execute_tool):
                # Perform one search and build a top-5 selection from it. Used as
                # the mock's whole strategy, and as a safety net for the real
                # model if it somehow answers without retrieving anything.
                execute_tool(
                    "search_topic",
                    {
                        "query": topic,
                        "language": target_language,
                        "max_results": max_results,
                    },
                )
                items = list(mcp.gathered.values())[:5]
                return SearchFilterResult(
                    selected=[
                        Source(
                            title=it.get("title") or it["url"],
                            url=it["url"],
                            relevance_score=min(max(it.get("score") or 0.85, 0.0), 1.0),
                            reason=(
                                f"Clear, reliable overview suitable for a "
                                f"{cefr_level} learner."
                            ),
                        )
                        for it in items
                    ]
                )

            selection = self.llm.structured_with_tools(
                system=SYSTEM_PROMPT,
                user=user,
                tools=mcp.tool_schemas(),
                execute_tool=mcp.call_tool,
                schema=SearchFilterResult,
                mock_bootstrap=seed_selection,
                max_tokens=4000,
                max_steps=settings.agent_max_steps,
            )

            # Safety net: if the model produced a selection without ever calling
            # the retrieval tool, there's no source material — retrieve now.
            if not mcp.gathered:
                selection = seed_selection(mcp.call_tool)

            selected = selection.selected[:5]
            materials = mcp.materials_for([s.url for s in selected])
            retrieved = len(mcp.gathered)

        return RetrievalOutcome(
            selection=SearchFilterResult(selected=selected),
            materials=materials,
            retrieved_count=retrieved,
        )
