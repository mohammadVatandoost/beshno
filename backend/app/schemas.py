"""Pydantic request/response schemas for the HTTP API."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .content_models import (
    AdaptedContent,
    EvaluationScores,
    ExerciseItemResult,
    PodcastScript,
    Source,
)
from .enums import CEFRLevel


# --------------------------------------------------------------------------
# Requests
# --------------------------------------------------------------------------
class PodcastCreate(BaseModel):
    native_language: str = Field(min_length=2, max_length=64)
    target_language: str = Field(min_length=2, max_length=64)
    cefr_level: CEFRLevel
    topic_category: Optional[str] = Field(default=None, max_length=120)
    topic_description: str = Field(min_length=3, max_length=2000)

    @field_validator("native_language", "target_language", "topic_description")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


# --------------------------------------------------------------------------
# Responses
# --------------------------------------------------------------------------
class StageEvent(BaseModel):
    stage: str
    label: str
    state: str
    at: str
    detail: Optional[str] = None


class EvaluationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    iteration: int
    passed: bool
    scores: EvaluationScores
    overall_score: float
    feedback: str
    revision_target: Optional[str] = None
    issues: list[str] = Field(default_factory=list)
    created_at: datetime


class AgentStepOut(BaseModel):
    """One logged step of the multi-agent pipeline, for step-by-step review."""

    model_config = ConfigDict(from_attributes=True)

    step_index: int
    agent: str
    stage: str
    iteration: int
    status: str
    inputs: Optional[dict] = None
    output: Optional[dict] = None
    detail: Optional[str] = None
    duration_ms: Optional[int] = None
    created_at: datetime


# --- Exercises (public shapes — answers withheld until grading) -----------
class SpeakingExerciseOut(BaseModel):
    prompt: str


class VocabExerciseOut(BaseModel):
    term: str
    question: str


class ReadingMCQExerciseOut(BaseModel):
    question: str
    options: list[str]


class ExerciseSetOut(BaseModel):
    """Exercises without answers/keys — safe to send before grading."""

    speaking: SpeakingExerciseOut
    vocabulary: list[VocabExerciseOut] = Field(default_factory=list)
    reading: list[ReadingMCQExerciseOut] = Field(default_factory=list)


class ExerciseGradeOut(BaseModel):
    score: int
    feedback: str
    items: list[ExerciseItemResult] = Field(default_factory=list)
    # Correct answers, revealed after submission so the learner can review.
    reading_correct_index: list[int] = Field(default_factory=list)
    vocabulary_reference: list[str] = Field(default_factory=list)


class PodcastSummary(BaseModel):
    """Compact representation used in the dashboard list."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
    native_language: str
    target_language: str
    cefr_level: str
    topic_category: Optional[str] = None
    topic_description: str
    title: Optional[str] = None
    status: str
    current_stage: str
    audio_duration_seconds: Optional[float] = None


class PodcastStatusOut(BaseModel):
    """Lightweight payload polled by the frontend during generation."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    status: str
    current_stage: str
    revision_count: int
    error_message: Optional[str] = None
    stage_history: list[StageEvent] = Field(default_factory=list)
    has_audio: bool = False


class PodcastDetail(PodcastSummary):
    """Full podcast record including agent artefacts."""

    error_message: Optional[str] = None
    revision_count: int = 0
    stage_history: list[StageEvent] = Field(default_factory=list)
    selected_sources: Optional[list[Source]] = None
    adapted_content: Optional[AdaptedContent] = None
    script: Optional[PodcastScript] = None
    evaluations: list[EvaluationOut] = Field(default_factory=list)
    exercises: Optional[ExerciseSetOut] = None
    audio_format: str = "wav"
    has_audio: bool = False
    has_exercises: bool = False


# --------------------------------------------------------------------------
# Metadata (drives the frontend form)
# --------------------------------------------------------------------------
class ProviderInfo(BaseModel):
    llm: str
    search: str
    tts: str


class MetaOut(BaseModel):
    topic_categories: list[str]
    languages: list[str]
    cefr_levels: list[str]
    providers: ProviderInfo
    max_revisions: int
