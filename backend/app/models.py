"""SQLAlchemy ORM models for podcasts and evaluation results."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base
from .enums import PodcastStatus, Stage


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Podcast(Base):
    __tablename__ = "podcasts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    # Owner placeholder — no auth yet, single implicit user. Kept for extensibility.
    owner: Mapped[str] = mapped_column(String(64), default="default", index=True)

    # --- Request parameters -------------------------------------------------
    native_language: Mapped[str] = mapped_column(String(64))
    target_language: Mapped[str] = mapped_column(String(64))
    cefr_level: Mapped[str] = mapped_column(String(2))
    topic_category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    topic_description: Mapped[str] = mapped_column(Text)

    # --- Generation state ---------------------------------------------------
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default=PodcastStatus.PENDING.value, index=True
    )
    current_stage: Mapped[str] = mapped_column(String(30), default=Stage.QUEUED.value)
    stage_history: Mapped[list] = mapped_column(JSON, default=list)
    revision_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Agent artefacts (stored as JSON) -----------------------------------
    selected_sources: Mapped[list | None] = mapped_column(JSON, nullable=True)
    adapted_content: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    script: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Timed transcript cues aligned to the audio (karaoke-style sync).
    transcript: Mapped[list | None] = mapped_column(JSON, nullable=True)
    exercises: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # --- Audio --------------------------------------------------------------
    audio_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    audio_format: Mapped[str] = mapped_column(String(8), default="wav")
    audio_duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    evaluations: Mapped[list["Evaluation"]] = relationship(
        back_populates="podcast",
        cascade="all, delete-orphan",
        order_by="Evaluation.iteration",
    )
    agent_steps: Mapped[list["AgentStep"]] = relationship(
        back_populates="podcast",
        cascade="all, delete-orphan",
        order_by="AgentStep.step_index",
    )
    attempts: Mapped[list["ExerciseAttempt"]] = relationship(
        back_populates="podcast",
        cascade="all, delete-orphan",
        order_by="ExerciseAttempt.created_at",
    )

    @property
    def has_audio(self) -> bool:
        return bool(self.audio_filename)

    @property
    def has_exercises(self) -> bool:
        return bool(self.exercises)


class Evaluation(Base):
    """Persisted Evaluator-agent verdict for transparency and tuning."""

    __tablename__ = "evaluations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    podcast_id: Mapped[str] = mapped_column(
        ForeignKey("podcasts.id", ondelete="CASCADE"), index=True
    )
    iteration: Mapped[int] = mapped_column(Integer, default=0)
    passed: Mapped[bool] = mapped_column(Boolean)
    scores: Mapped[dict] = mapped_column(JSON)
    overall_score: Mapped[float] = mapped_column(Float)
    feedback: Mapped[str] = mapped_column(Text, default="")
    revision_target: Mapped[str | None] = mapped_column(String(30), nullable=True)
    issues: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    podcast: Mapped[Podcast] = relationship(back_populates="evaluations")


class AgentStep(Base):
    """One step of the multi-agent pipeline, logged for step-by-step review.

    Every agent invocation (and the audio step) appends a row keyed by the
    podcast/session id, capturing the agent's name, the stage, its inputs and
    its output, so the whole architecture can be replayed after the fact.
    """

    __tablename__ = "agent_steps"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    podcast_id: Mapped[str] = mapped_column(
        ForeignKey("podcasts.id", ondelete="CASCADE"), index=True
    )
    # Monotonic order of this step within the session (0-based).
    step_index: Mapped[int] = mapped_column(Integer, default=0)
    # The agent that ran this step (e.g. "search_filter", "scriptwriter", "tts").
    agent: Mapped[str] = mapped_column(String(64), index=True)
    # The pipeline stage the step belongs to.
    stage: Mapped[str] = mapped_column(String(30))
    # Revision iteration (0 on the first pass; >0 for evaluator-driven redos).
    iteration: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="ok")  # ok | error
    inputs: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    podcast: Mapped[Podcast] = relationship(back_populates="agent_steps")


class ExerciseAttempt(Base):
    """A learner's submission to a podcast's exercise set, with its grade."""

    __tablename__ = "exercise_attempts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    podcast_id: Mapped[str] = mapped_column(
        ForeignKey("podcasts.id", ondelete="CASCADE"), index=True
    )
    submission: Mapped[dict] = mapped_column(JSON)
    score: Mapped[int] = mapped_column(Integer)
    feedback: Mapped[str] = mapped_column(Text, default="")
    items: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    podcast: Mapped[Podcast] = relationship(back_populates="attempts")


class UserLearnedVocabulary(Base):
    """Difficult words/phrases already taught to a user, for spaced repetition.

    Lets later podcasts avoid re-introducing the same vocabulary. Scoped by
    ``owner`` (user id) and ``target_language`` so a learner studying two
    languages keeps separate word histories. ``podcast_id`` is a soft reference
    (no FK) so a learned word survives deletion of the podcast that taught it.
    """

    __tablename__ = "user_learned_vocabulary"
    __table_args__ = (
        UniqueConstraint(
            "owner", "target_language", "term", name="uq_learned_vocab_owner_lang_term"
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    owner: Mapped[str] = mapped_column(String(64), index=True)
    target_language: Mapped[str] = mapped_column(String(64), index=True)
    term: Mapped[str] = mapped_column(String(255))
    meaning: Mapped[str | None] = mapped_column(Text, nullable=True)
    podcast_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
