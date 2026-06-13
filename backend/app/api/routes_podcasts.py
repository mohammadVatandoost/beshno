"""HTTP routes for podcast creation, listing, status polling and audio."""

from __future__ import annotations

import os

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..enums import CEFRLevel, PodcastStatus, Stage
from ..languages import COMMON_LANGUAGES
from ..models import Podcast
from ..pipeline import generate_podcast
from ..schemas import (
    MetaOut,
    PodcastCreate,
    PodcastDetail,
    PodcastStatusOut,
    PodcastSummary,
    ProviderInfo,
)
from ..storage import Storage

router = APIRouter(prefix="/api")

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
    background: BackgroundTasks,
    db: Session = Depends(get_db),
) -> Podcast:
    podcast = Podcast(
        native_language=payload.native_language,
        target_language=payload.target_language,
        cefr_level=payload.cefr_level.value,
        topic_category=payload.topic_category,
        topic_description=payload.topic_description,
        status=PodcastStatus.PENDING.value,
        current_stage=Stage.QUEUED.value,
        stage_history=[],
    )
    db.add(podcast)
    db.commit()
    db.refresh(podcast)

    # Kick off the multi-agent pipeline in the background (threadpool for sync fn).
    background.add_task(generate_podcast, podcast.id)
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
