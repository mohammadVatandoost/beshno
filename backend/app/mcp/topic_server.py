"""MCP server exposing the topic-retrieval (web search) API as a tool.

Run over stdio as a subprocess by the pipeline's MCP client:

    python -m app.mcp.topic_server

It wraps whatever SearchProvider the app is configured to use (Tavily, or the
mock), so the agent calling ``search_topic`` transparently hits the real search
backend when ``TAVILY_API_KEY`` is set and the deterministic mock otherwise.

Configuration flows through the environment (the same ``.env`` the app reads),
since the server runs in its own process.
"""

from __future__ import annotations

import logging
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ..config import get_settings
from ..providers import get_search

log = logging.getLogger(__name__)

mcp = FastMCP("beshno-topic-retrieval")


@mcp.tool()
def search_topic(
    query: Annotated[
        str, Field(description="The search query — the topic to research.")
    ],
    language: Annotated[
        str,
        Field(
            description="The language to bias results toward (e.g. 'Spanish', 'French')."
        ),
    ],
    max_results: Annotated[
        int, Field(description="Maximum number of results to return.", ge=1, le=20)
    ] = 10,
) -> dict:
    """Search the web for reliable, substantive resources about a topic.

    Returns a list of results, each with a title, URL, relevance score, and the
    page content. Call this to gather source material before selecting the best
    references; you may call it more than once with refined queries.
    """
    settings = get_settings()
    search = get_search(settings)
    results = search.search(query, language=language, max_results=max_results)
    log.info("search_topic(%r, language=%r) -> %d results", query, language, len(results))
    return {
        "provider": search.name,
        "query": query,
        "results": [
            {
                "title": r.title,
                "url": r.url,
                "score": r.score,
                "content": r.content,
            }
            for r in results
        ],
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
