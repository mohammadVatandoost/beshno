"""Enumerations and ordered stage metadata shared across the backend."""

from __future__ import annotations

from enum import Enum


class PodcastStatus(str, Enum):
    """Lifecycle status of a podcast generation job."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    READY = "ready"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"


class Stage(str, Enum):
    """Discrete stages of the multi-agent generation pipeline."""

    QUEUED = "queued"
    RESEARCHING = "researching"
    FILTERING = "filtering"
    ADAPTING = "adapting"
    SCRIPTING = "scripting"
    EVALUATING = "evaluating"
    GENERATING_AUDIO = "generating_audio"
    DONE = "done"


class CEFRLevel(str, Enum):
    """Common European Framework of Reference language proficiency levels."""

    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"


class StageState(str, Enum):
    """State of an individual stage within the recorded stage history."""

    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"


# The ordered stages surfaced in the UI progress tracker (QUEUED/DONE are implicit).
STAGE_ORDER: list[Stage] = [
    Stage.RESEARCHING,
    Stage.FILTERING,
    Stage.ADAPTING,
    Stage.SCRIPTING,
    Stage.EVALUATING,
    Stage.GENERATING_AUDIO,
]

# Human-readable labels matching the product spec.
STAGE_LABELS: dict[Stage, str] = {
    Stage.QUEUED: "Queued",
    Stage.RESEARCHING: "Researching topic",
    Stage.FILTERING: "Selecting sources",
    Stage.ADAPTING: "Adapting content",
    Stage.SCRIPTING: "Writing script",
    Stage.EVALUATING: "Reviewing quality",
    Stage.GENERATING_AUDIO: "Generating audio",
    Stage.DONE: "Ready",
}
