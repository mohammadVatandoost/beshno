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
    EXERCISES = "exercises"
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
    Stage.EXERCISES,
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
    Stage.EXERCISES: "Creating exercises",
    Stage.DONE: "Ready",
}

# Advanced levels get a monolingual, target-language-only ("immersion") episode;
# A1/A2/B1 get the dual-language (target + native breakdown) episode.
_IMMERSION_LEVELS = {"B2", "C1", "C2"}


def is_immersion_level(cefr_level: str) -> bool:
    """True for levels above B1, where the episode is 100% in the target language."""
    return (cefr_level or "").strip().upper() in _IMMERSION_LEVELS


# --------------------------------------------------------------------------
# Podcast duration (user-selected target runtime)
# --------------------------------------------------------------------------
# The strict set of runtimes the user may pick, in minutes.
PODCAST_DURATIONS: list[int] = [5, 10, 20, 30]
DEFAULT_DURATION_MINUTES = 10

# Per-duration content budget that drives Agent 2 (adapted-text size) and Agent 3
# (segment count). Rough model: the target content is spoken ~twice (full
# playback + per-segment replay) plus native/target breakdowns, at ~140 wpm — so
# adapted-text words ≈ runtime_minutes * ~45. Values are guidance, not hard caps.
_DURATION_PLANS: dict[int, dict[str, int]] = {
    5: {"target_words": 220, "segments": 6},
    10: {"target_words": 450, "segments": 10},
    20: {"target_words": 950, "segments": 16},
    30: {"target_words": 1400, "segments": 22},
}


def normalize_duration(minutes: int | None) -> int:
    """Clamp an arbitrary value to the nearest allowed duration option."""
    if minutes in _DURATION_PLANS:
        return int(minutes)  # exact match
    if not minutes or minutes <= 0:
        return DEFAULT_DURATION_MINUTES
    return min(PODCAST_DURATIONS, key=lambda d: abs(d - int(minutes)))


def duration_plan(minutes: int | None) -> dict[str, int]:
    """Content budget (target word count, segment count) for a runtime."""
    return _DURATION_PLANS[normalize_duration(minutes)]


# --------------------------------------------------------------------------
# Narrator tone / persona
# --------------------------------------------------------------------------
class Tone(str, Enum):
    """User-selectable narrator/script tone. AUTO is resolved from the topic."""

    AUTO = "auto"
    DEFAULT = "default"
    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"
    CANDID = "candid"
    QUIRKY = "quirky"
    EFFICIENT = "efficient"
    NERDY = "nerdy"
    CYNICAL = "cynical"


DEFAULT_TONE = Tone.AUTO

# Style directive injected into the generative agents, per concrete tone. Tone
# shapes style only — never the CEFR level, the facts, or the required format.
TONE_GUIDANCE: dict[Tone, str] = {
    Tone.DEFAULT: "Neutral, balanced and standard — helpful and clear with no stylistic quirks.",
    Tone.PROFESSIONAL: "Crisp, formal and polished; precise, businesslike and authoritative.",
    Tone.FRIENDLY: "Warm, approachable and conversational, with natural transitions and gentle encouragement.",
    Tone.CANDID: "Direct and straightforward — state things cleanly and honestly, without hedging or sugarcoating.",
    Tone.QUIRKY: "Playful, creative and lightly humorous, with the occasional unexpected analogy or aside (tasteful and on-topic).",
    Tone.EFFICIENT: "Ultra-concise — drop pleasantries and preamble; use the shortest clear phrasing that still teaches.",
    Tone.NERDY: "Analytical and highly structured; lean into technical, scientific or mathematical detail and precise terminology.",
    Tone.CYNICAL: "Mildly skeptical, dryly sarcastic and bluntly realistic — without becoming negative, mean or unhelpful.",
}

TONE_LABELS: dict[Tone, str] = {
    Tone.AUTO: "Auto",
    Tone.DEFAULT: "Default",
    Tone.PROFESSIONAL: "Professional",
    Tone.FRIENDLY: "Friendly",
    Tone.CANDID: "Candid",
    Tone.QUIRKY: "Quirky",
    Tone.EFFICIENT: "Efficient",
    Tone.NERDY: "Nerdy",
    Tone.CYNICAL: "Cynical",
}

TONE_DESCRIPTIONS: dict[Tone, str] = {
    Tone.AUTO: "Match the tone to the topic automatically.",
    Tone.DEFAULT: "Neutral, balanced, standard delivery.",
    Tone.PROFESSIONAL: "Crisp, formal and polished.",
    Tone.FRIENDLY: "Warm, approachable and conversational.",
    Tone.CANDID: "Direct and straightforward, no fluff.",
    Tone.QUIRKY: "Playful, creative and humorous.",
    Tone.EFFICIENT: "Ultra-concise; minimal words.",
    Tone.NERDY: "Analytical and deeply technical.",
    Tone.CYNICAL: "Skeptical, dry and bluntly realistic.",
}


def tone_directive(tone: str | None) -> str:
    """Style directive for a concrete tone (AUTO/unknown -> Default)."""
    try:
        t = Tone((tone or "").strip().lower())
    except ValueError:
        t = Tone.DEFAULT
    if t == Tone.AUTO:
        t = Tone.DEFAULT
    return TONE_GUIDANCE[t]


def tone_options() -> list[dict]:
    """[{value, label, description}] for the frontend form (Auto first)."""
    return [
        {"value": t.value, "label": TONE_LABELS[t], "description": TONE_DESCRIPTIONS[t]}
        for t in Tone
    ]
