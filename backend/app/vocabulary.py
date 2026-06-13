"""Repository for the user's learned vocabulary (spaced-repetition tracking).

A single place that reads/writes the ``user_learned_vocabulary`` table. The MCP
vocab server calls these with its own session; the pipeline calls them with the
orchestrator's session — so there is one implementation of the table access.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import UserLearnedVocabulary

log = logging.getLogger(__name__)


def fetch_learned_terms(
    db: Session, *, owner: str, target_language: str, limit: int = 300
) -> list[dict]:
    """Words already taught to ``owner`` in ``target_language`` (newest first)."""
    rows = (
        db.execute(
            select(UserLearnedVocabulary)
            .where(
                UserLearnedVocabulary.owner == owner,
                UserLearnedVocabulary.target_language == target_language,
            )
            .order_by(UserLearnedVocabulary.created_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return [{"term": r.term, "meaning": r.meaning} for r in rows]


def record_terms(
    db: Session,
    *,
    owner: str,
    target_language: str,
    items: Iterable[tuple[str, str | None]],
    podcast_id: str | None = None,
) -> int:
    """Persist newly-taught (term, meaning) pairs, skipping ones already stored.

    Dedupes case-insensitively against the existing history and within the batch
    so re-recording the same word is a no-op. Returns the number actually added.
    """
    existing = {
        t.lower()
        for t in db.execute(
            select(UserLearnedVocabulary.term).where(
                UserLearnedVocabulary.owner == owner,
                UserLearnedVocabulary.target_language == target_language,
            )
        )
        .scalars()
        .all()
    }
    seen = set(existing)
    added = 0
    for term, meaning in items:
        term = (term or "").strip()
        if not term:
            continue
        key = term.lower()
        if key in seen:
            continue
        seen.add(key)
        db.add(
            UserLearnedVocabulary(
                owner=owner,
                target_language=target_language,
                term=term,
                meaning=meaning,
                podcast_id=podcast_id,
            )
        )
        added += 1
    if added:
        db.commit()
    return added
