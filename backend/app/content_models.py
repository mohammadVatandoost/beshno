"""Domain content models shared by agents, the pipeline, and API schemas.

These Pydantic models double as the structured-output schemas the agents ask
Claude to fill, and as the canonical JSON shapes persisted to the database.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class Source(BaseModel):
    """A reference resource selected by the Search Filter agent."""

    title: str
    url: str
    relevance_score: float = Field(ge=0, le=1, description="0..1 relevance to the topic")
    reason: str = Field(description="Why this source was selected")


class KeyVocab(BaseModel):
    """A vocabulary item with a learner-friendly explanation."""

    term: str
    meaning: str = Field(description="Explanation in the learner's native language")


class AdaptedContent(BaseModel):
    """Output of the Content Adapter agent — CEFR-aligned summary of sources."""

    title: str
    adapted_text: str = Field(description="The CEFR-adapted summary (<= ~5 pages)")
    key_points: list[str] = Field(default_factory=list)
    key_vocabulary: list[KeyVocab] = Field(default_factory=list)


class ExplanationRun(BaseModel):
    """A run of the breakdown in a single language, so each is voiced correctly."""

    lang: Literal["native", "target"] = Field(
        description="'native' for commentary in the learner's native language; "
        "'target' for a word or phrase quoted in the target (learning) language"
    )
    text: str


class ContentSegment(BaseModel):
    """One short chunk of the content paired with its native-language breakdown."""

    target_text: str = Field(
        description="A short, self-contained chunk of the content in the target "
        "(learning) language, at the learner's CEFR level"
    )
    native_explanation: list[ExplanationRun] = Field(
        default_factory=list,
        description="The breakdown as an ordered list of language-tagged runs. Keep "
        "native-language commentary in lang='native' runs and put every "
        "target-language word/phrase in its OWN lang='target' run, so the audio "
        "pronounces each part with the correct voice (rather than the native voice "
        "reading foreign words with native phonetics)",
    )


class PodcastScript(BaseModel):
    """Output of the Scriptwriter agent — a dual-language, two-phase episode.

    Phase 1 (full playback) reads every segment's ``target_text`` in order,
    smoothly and uninterrupted, in the target language. Phase 2 (segmented
    translation) replays each segment followed by its ``native_explanation``.
    """

    title: str
    intro: str = Field(
        default="",
        description="A short spoken intro in the NATIVE language: welcomes the "
        "listener, names the topic, and explains the two-part format",
    )
    breakdown_intro: str = Field(
        default="",
        description="A short NATIVE-language cue spoken between the two phases, "
        "e.g. 'Now let's go through it piece by piece.'",
    )
    segments: list[ContentSegment] = Field(default_factory=list)


class EvaluationScores(BaseModel):
    """Per-dimension quality scores (0..5) produced by the Evaluator agent."""

    cefr_compliance: float = Field(ge=0, le=5)
    language_balance: float = Field(ge=0, le=5)
    pedagogical_quality: float = Field(ge=0, le=5)
    factual_accuracy: float = Field(ge=0, le=5)
    engagement_flow: float = Field(ge=0, le=5)


class EvaluationResult(BaseModel):
    """Output of the Evaluator agent — the quality gate verdict."""

    passed: bool
    scores: EvaluationScores
    overall_score: float = Field(ge=0, le=5)
    feedback: str = Field(description="Actionable feedback for the next revision")
    revision_target: Optional[Literal["content_adapter", "scriptwriter"]] = Field(
        default=None,
        description="Which agent should revise on failure (null if passed)",
    )
    issues: list[str] = Field(default_factory=list)
