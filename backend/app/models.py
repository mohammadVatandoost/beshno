"""SQLAlchemy ORM models for podcasts and evaluation results."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
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

    # --- Audio --------------------------------------------------------------
    audio_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    audio_format: Mapped[str] = mapped_column(String(8), default="wav")
    audio_duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    evaluations: Mapped[list["Evaluation"]] = relationship(
        back_populates="podcast",
        cascade="all, delete-orphan",
        order_by="Evaluation.iteration",
    )

    @property
    def has_audio(self) -> bool:
        return bool(self.audio_filename)


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
