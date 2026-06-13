"""MCP server exposing the user's learned-vocabulary table as tools.

Run over stdio as a subprocess by the pipeline's MCP client:

    python -m app.mcp.vocab_server

It lets the Content Adapter and Scriptwriter agents query which difficult words
were already taught to a user (so they avoid repeating them) and lets the
pipeline record newly-taught words. Configuration (DATABASE_URL) flows through
the environment, since the server runs in its own process.
"""

from __future__ import annotations

import logging
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from .. import vocabulary
from ..database import SessionLocal

log = logging.getLogger(__name__)

mcp = FastMCP("beshno-learned-vocabulary")


@mcp.tool()
def get_learned_vocabulary(
    owner: Annotated[str, Field(description="The user / owner id.")],
    target_language: Annotated[
        str, Field(description="The language the user is learning (e.g. 'Spanish').")
    ],
    limit: Annotated[
        int, Field(description="Maximum number of terms to return.", ge=1, le=1000)
    ] = 300,
) -> dict:
    """Difficult words/phrases ALREADY taught to this user in this language.

    Agents must AVOID re-introducing, re-defining, or focusing on these words so
    each new podcast teaches fresh, level-appropriate vocabulary.
    """
    db = SessionLocal()
    try:
        items = vocabulary.fetch_learned_terms(
            db, owner=owner, target_language=target_language, limit=limit
        )
    finally:
        db.close()
    log.info(
        "get_learned_vocabulary(owner=%r, lang=%r) -> %d term(s)",
        owner,
        target_language,
        len(items),
    )
    return {
        "owner": owner,
        "target_language": target_language,
        "terms": [it["term"] for it in items],
        "items": items,
    }


@mcp.tool()
def record_learned_vocabulary(
    owner: Annotated[str, Field(description="The user / owner id.")],
    target_language: Annotated[str, Field(description="The language being learned.")],
    terms: Annotated[list[str], Field(description="Newly-taught words/phrases.")],
    meanings: Annotated[
        list[str] | None,
        Field(description="Optional meanings, aligned by index with terms."),
    ] = None,
    podcast_id: Annotated[
        str | None, Field(description="The podcast that taught these words.")
    ] = None,
) -> dict:
    """Record newly-taught words so future podcasts can avoid repeating them."""
    db = SessionLocal()
    try:
        pairs = [
            (t, (meanings[i] if meanings and i < len(meanings) else None))
            for i, t in enumerate(terms)
        ]
        added = vocabulary.record_terms(
            db,
            owner=owner,
            target_language=target_language,
            items=pairs,
            podcast_id=podcast_id,
        )
    finally:
        db.close()
    return {"recorded": added}


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
