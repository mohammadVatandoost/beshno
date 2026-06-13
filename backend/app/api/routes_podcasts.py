"""HTTP routes for podcast creation, listing, status polling and audio."""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agents import ExerciseGraderAgent
from ..config import get_settings
from ..content_models import ExerciseSet, ExerciseSubmission
from ..database import get_db
from ..enums import CEFRLevel, PODCAST_DURATIONS, PodcastStatus, Stage, tone_options
from ..languages import COMMON_LANGUAGES
from ..models import AgentStep, ExerciseAttempt, Podcast
from ..pipeline import submit_generation
from ..providers import get_llm
from ..schemas import (
    AgentStepOut,
    ExerciseGradeOut,
    MetaOut,
    PodcastCreate,
    PodcastDetail,
    PodcastStatusOut,
    PodcastSummary,
    ProviderInfo,
)
from ..storage import Storage

router = APIRouter(prefix="/api")

log = logging.getLogger(__name__)

TOPIC_CATEGORIES = [
    "Technology",
    "Science",
    "History",
    "Culture & Society",
    "Business & Economics",
    "Health & Wellness",
    "Travel",
    "Sports",
    "Arts & Literature",
    "Nature & Environment",
    "Food & Cooking",
    "Daily Life",
]


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/meta", response_model=MetaOut)
def meta() -> MetaOut:
    s = get_settings()
    return MetaOut(
        topic_categories=TOPIC_CATEGORIES,
        languages=COMMON_LANGUAGES,
        cefr_levels=[lvl.value for lvl in CEFRLevel],
        durations=PODCAST_DURATIONS,
        tones=tone_options(),
        providers=ProviderInfo(
            llm=s.resolved_llm_provider(),
            search=s.resolved_search_provider(),
            tts=s.resolved_tts_provider(),
        ),
        max_revisions=s.max_revisions,
    )


@router.post("/podcasts", response_model=PodcastDetail, status_code=201)
def create_podcast(
    payload: PodcastCreate,
    db: Session = Depends(get_db),
) -> Podcast:
    podcast = Podcast(
        native_language=payload.native_language,
        target_language=payload.target_language,
        cefr_level=payload.cefr_level.value,
        topic_category=payload.topic_category,
        topic_description=payload.topic_description,
        duration_minutes=payload.duration_minutes,
        tone=payload.tone.value,
        status=PodcastStatus.PENDING.value,
        current_stage=Stage.QUEUED.value,
        stage_history=[],
    )
    db.add(podcast)
    db.commit()
    db.refresh(podcast)

    log.info(
        "podcast %s created (%s -> %s, %s); queued for background generation",
        podcast.id,
        payload.native_language,
        payload.target_language,
        payload.cefr_level.value,
    )
    # Dispatch to the dedicated generation worker pool and return immediately —
    # the HTTP response does not wait for the agents to run.
    submit_generation(podcast.id)
    return podcast


@router.get("/podcasts", response_model=list[PodcastSummary])
def list_podcasts(db: Session = Depends(get_db)) -> list[Podcast]:
    rows = db.execute(select(Podcast).order_by(Podcast.created_at.desc())).scalars().all()
    return list(rows)


@router.get("/podcasts/{podcast_id}", response_model=PodcastDetail)
def get_podcast(podcast_id: str, db: Session = Depends(get_db)) -> Podcast:
    podcast = db.get(Podcast, podcast_id)
    if podcast is None:
        raise HTTPException(status_code=404, detail="Podcast not found")
    return podcast


@router.get("/podcasts/{podcast_id}/status", response_model=PodcastStatusOut)
def get_status(podcast_id: str, db: Session = Depends(get_db)) -> Podcast:
    podcast = db.get(Podcast, podcast_id)
    if podcast is None:
        raise HTTPException(status_code=404, detail="Podcast not found")
    return podcast


@router.get("/podcasts/{podcast_id}/steps", response_model=list[AgentStepOut])
def get_steps(podcast_id: str, db: Session = Depends(get_db)) -> list[AgentStep]:
    """Return the logged agent steps for a session, ordered, for review."""
    if db.get(Podcast, podcast_id) is None:
        raise HTTPException(status_code=404, detail="Podcast not found")
    rows = (
        db.execute(
            select(AgentStep)
            .where(AgentStep.podcast_id == podcast_id)
            .order_by(AgentStep.step_index)
        )
        .scalars()
        .all()
    )
    return list(rows)


@router.post("/podcasts/{podcast_id}/exercises/submit", response_model=ExerciseGradeOut)
def submit_exercises(
    podcast_id: str,
    submission: ExerciseSubmission,
    db: Session = Depends(get_db),
) -> ExerciseGradeOut:
    """Grade a learner's exercise answers: a 1-10 score and teacher feedback."""
    podcast = db.get(Podcast, podcast_id)
    if podcast is None:
        raise HTTPException(status_code=404, detail="Podcast not found")
    if not podcast.exercises:
        raise HTTPException(status_code=404, detail="No exercises for this podcast")

    ex_set = ExerciseSet.model_validate(podcast.exercises)
    reading_correct = [r.correct_index for r in ex_set.reading]
    mcq_correct = [
        (submission.reading_answers[i] if i < len(submission.reading_answers) else -1)
        == r.correct_index
        for i, r in enumerate(ex_set.reading)
    ]

    grade = ExerciseGraderAgent(get_llm()).run(
        exercise_set=ex_set,
        submission=submission,
        target_language=podcast.target_language,
        native_language=podcast.native_language,
        cefr_level=podcast.cefr_level,
        mcq_correct=mcq_correct,
    )

    db.add(
        ExerciseAttempt(
            podcast_id=podcast.id,
            submission=submission.model_dump(),
            score=grade.score,
            feedback=grade.feedback,
            items=[it.model_dump() for it in grade.items],
        )
    )
    db.commit()

    return ExerciseGradeOut(
        score=grade.score,
        feedback=grade.feedback,
        items=grade.items,
        reading_correct_index=reading_correct,
        vocabulary_reference=[v.answer for v in ex_set.vocabulary],
    )


@router.get("/podcasts/{podcast_id}/audio")
def get_audio(podcast_id: str, db: Session = Depends(get_db)) -> FileResponse:
    podcast = db.get(Podcast, podcast_id)
    if podcast is None:
        raise HTTPException(status_code=404, detail="Podcast not found")
    if not podcast.audio_filename:
        raise HTTPException(status_code=404, detail="Audio not ready")

    path = Storage().audio_path(podcast.id, podcast.audio_format)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Audio file missing on disk")

    safe_title = (podcast.title or "podcast").replace("/", "-")[:80]
    return FileResponse(
        path,
        media_type="audio/wav",
        filename=f"{safe_title}.{podcast.audio_format}",
    )


@router.delete("/podcasts/{podcast_id}", status_code=204)
def delete_podcast(podcast_id: str, db: Session = Depends(get_db)) -> None:
    podcast = db.get(Podcast, podcast_id)
    if podcast is None:
        raise HTTPException(status_code=404, detail="Podcast not found")
    if podcast.audio_filename:
        path = Storage().audio_path(podcast.id, podcast.audio_format)
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass
    db.delete(podcast)
    db.commit()
