"""Runs the full multi-agent podcast generation pipeline.

    [search] -> Agent 1 filter -> Agent 2 adapt -> Agent 3 script
            -> Agent 4 evaluate (loop back to 2/3 on failure) -> TTS -> store

Designed to run in a background thread with its own DB session. All progress,
agent artefacts and evaluator verdicts are persisted as the pipeline advances so
the frontend can poll stage-level status.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..agents import (
    ContentAdapterAgent,
    EvaluatorAgent,
    ExerciseGeneratorAgent,
    ScriptwriterAgent,
    SearchFilterAgent,
)
from ..config import Settings, get_settings
from ..content_models import PodcastScript
from ..database import SessionLocal
from ..enums import (
    PodcastStatus,
    Stage,
    StageState,
    STAGE_LABELS,
    is_immersion_level,
)
from ..languages import to_bcp47
from ..models import AgentStep, Evaluation, Podcast
from ..providers import get_llm, get_search, get_tts
from ..providers.tts.base import SpeechSegment
from ..storage import Storage
from ..vocabulary import record_terms

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Stage-history / status helpers (JSON column reassigned to flag the change)
# --------------------------------------------------------------------------
def _append_event(
    podcast: Podcast, stage: Stage, state: StageState, detail: str | None = None
) -> None:
    event = {
        "stage": stage.value,
        "label": STAGE_LABELS[stage],
        "state": state.value,
        "at": datetime.now(timezone.utc).isoformat(),
        "detail": detail,
    }
    podcast.stage_history = (podcast.stage_history or []) + [event]


def _start_stage(db: Session, podcast: Podcast, stage: Stage) -> None:
    podcast.status = PodcastStatus.IN_PROGRESS.value
    podcast.current_stage = stage.value
    _append_event(podcast, stage, StageState.STARTED)
    db.commit()
    log.info("podcast=%s stage=%s started", podcast.id, stage.value)


def _complete_stage(
    db: Session, podcast: Podcast, stage: Stage, detail: str | None = None
) -> None:
    _append_event(podcast, stage, StageState.COMPLETED, detail)
    db.commit()


def _log_step(
    db: Session,
    podcast: Podcast,
    *,
    index: int,
    agent: str,
    stage: Stage,
    output: dict | None = None,
    inputs: dict | None = None,
    iteration: int = 0,
    status: str = "ok",
    detail: str | None = None,
    duration_ms: int | None = None,
) -> None:
    """Persist one agent step for later step-by-step review of the run."""
    db.add(
        AgentStep(
            podcast_id=podcast.id,
            step_index=index,
            agent=agent,
            stage=stage.value,
            iteration=iteration,
            status=status,
            inputs=inputs,
            output=output,
            detail=detail,
            duration_ms=duration_ms,
        )
    )
    db.commit()
    log.info(
        "podcast=%s step=%d agent=%s stage=%s status=%s",
        podcast.id,
        index,
        agent,
        stage.value,
        status,
    )


def _format_feedback(feedback: str, issues: list[str]) -> str:
    if not issues:
        return feedback
    bullets = "\n".join(f"- {i}" for i in issues)
    return f"{feedback}\n\nSpecific issues:\n{bullets}"


def _script_to_segments(
    script: PodcastScript,
    target_language: str,
    native_language: str,
    immersion: bool = False,
) -> list[SpeechSegment]:
    """Build the two-phase audio track.

    1. Intro (explains the format).
    2. Full playback: every segment's target text, read near-seamlessly.
    3. Cue introducing the breakdown.
    4. Each target chunk, then its breakdown, with a clear pause between chunks.

    Content uses a female voice, the explainer a male voice. In dual-language
    mode (A1-B1) the intro/cues/breakdowns are native-language; in immersion mode
    (B2+) the entire track is in the target language.
    """
    target_code = to_bcp47(target_language)
    native_code = to_bcp47(native_language)
    CONTENT_VOICE = "female"  # learner / content voice
    EXPLAIN_VOICE = "male"  # teacher / explainer voice
    cue_code = target_code if immersion else native_code
    cue_lang = "target" if immersion else "native"
    segments: list[SpeechSegment] = []

    if script.intro.strip():
        segments.append(
            SpeechSegment(
                script.intro,
                cue_code,
                EXPLAIN_VOICE,
                pause_after=0.7,
                cue={"kind": "intro", "phase": "intro", "group": None, "lang": cue_lang},
            )
        )

    # Phase 1 — full playback in the target language, uninterrupted.
    for i, seg in enumerate(script.segments):
        if seg.target_text.strip():
            segments.append(
                SpeechSegment(
                    seg.target_text,
                    target_code,
                    CONTENT_VOICE,
                    pause_after=0.12,
                    cue={"kind": "full", "phase": "playback", "group": i, "lang": "target"},
                )
            )

    if script.breakdown_intro.strip():
        segments.append(
            SpeechSegment(
                script.breakdown_intro,
                cue_code,
                EXPLAIN_VOICE,
                pause_after=0.7,
                cue={
                    "kind": "breakdown_intro",
                    "phase": "breakdown",
                    "group": None,
                    "lang": cue_lang,
                },
            )
        )

    # Phase 2 — each chunk, then its breakdown.
    for i, seg in enumerate(script.segments):
        if seg.target_text.strip():
            segments.append(
                SpeechSegment(
                    seg.target_text,
                    target_code,
                    CONTENT_VOICE,
                    pause_after=0.25,
                    cue={"kind": "segment", "phase": "breakdown", "group": i, "lang": "target"},
                )
            )
        runs = [r for r in seg.native_explanation if r.text.strip()]
        for j, run in enumerate(runs):
            gap = 0.8 if j == len(runs) - 1 else 0.06
            if immersion:
                # Whole episode is in the target language; the explainer voice
                # delivers the deeper explanation in the target language.
                code, voice, lang = target_code, EXPLAIN_VOICE, "target"
            elif run.lang == "target":
                # A target word quoted inside a native breakdown — target voice
                # so it is pronounced correctly (not with native phonetics).
                code, voice, lang = target_code, CONTENT_VOICE, "target"
            else:
                code, voice, lang = native_code, EXPLAIN_VOICE, "native"
            segments.append(
                SpeechSegment(
                    run.text,
                    code,
                    voice,
                    pause_after=gap,
                    cue={"kind": "explanation", "phase": "breakdown", "group": i, "lang": lang},
                )
            )
    return segments


def _build_transcript(segments: list[SpeechSegment], timings: list) -> list[dict]:
    """Align speech segments with their measured timings into transcript cues."""
    cues: list[dict] = []
    for seg, timing in zip(segments, timings):
        if seg.cue is None:
            continue
        cues.append(
            {
                "index": len(cues),
                **seg.cue,
                "text": seg.text,
                "start": round(timing.start, 3),
                "end": round(timing.end, 3),
            }
        )
    return cues


def _open_vocab_mcp(owner: str):
    """Start the learned-vocabulary MCP session, or None if unavailable.

    Best-effort: vocabulary avoidance is an optimization, so any failure to start
    the MCP server is logged and generation proceeds without it.
    """
    try:
        from ..mcp import LearnedVocabMCP

        return LearnedVocabMCP().open()
    except Exception as exc:  # noqa: BLE001 - avoidance is best-effort
        log.warning(
            "learned-vocab MCP unavailable (%s); generating without vocab avoidance",
            exc,
        )
        return None


def _close_vocab_mcp(vocab_mcp) -> None:
    try:
        vocab_mcp.close()
    except Exception:  # pragma: no cover - best-effort cleanup
        pass


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------
def generate_podcast(podcast_id: str) -> None:
    """Run the pipeline for a podcast. Safe to call from a background thread."""
    settings = get_settings()
    storage = Storage()
    storage.ensure()

    llm = get_llm(settings)
    # The MCP topic-retrieval server resolves the search provider in its own
    # process; we resolve it here too purely to log which backend will be used.
    search = get_search(settings)
    tts = get_tts(settings)
    log.info(
        "podcast=%s providers: llm=%s search=%s (via MCP) tts=%s",
        podcast_id,
        llm.name,
        search.name,
        tts.name,
    )

    db = SessionLocal()
    vocab_mcp = None
    try:
        podcast = db.get(Podcast, podcast_id)
        if podcast is None:
            log.error("generate_podcast: podcast %s not found", podcast_id)
            return
        # One shared learned-vocabulary MCP session for this generation, queried
        # by Agent 2 and Agent 3 to avoid repeating previously-taught words.
        vocab_mcp = _open_vocab_mcp(podcast.owner)
        try:
            _run(db, podcast, settings, storage, llm, tts, vocab_mcp)
        except Exception as exc:  # noqa: BLE001 - record any failure on the record
            log.exception("Pipeline failed for podcast %s", podcast_id)
            podcast.status = PodcastStatus.FAILED.value
            podcast.error_message = str(exc)[:1000]
            try:
                _append_event(
                    podcast, Stage(podcast.current_stage), StageState.FAILED, str(exc)[:300]
                )
            except Exception:  # pragma: no cover - current_stage always valid
                pass
            db.commit()
    finally:
        if vocab_mcp is not None:
            _close_vocab_mcp(vocab_mcp)
        db.close()


def _run(
    db: Session,
    podcast: Podcast,
    settings: Settings,
    storage: Storage,
    llm,
    tts,
    vocab_mcp=None,
) -> None:
    target = podcast.target_language
    native = podcast.native_language
    cefr = podcast.cefr_level
    topic = podcast.topic_description
    step_no = 0  # monotonic index of agent steps logged for this session

    # --- Stages 1-2: agentic research + filter -----------------------------
    # Agent 1 retrieves sources by calling the topic-retrieval MCP tool itself
    # (possibly several times with refined queries) and selects the best ones.
    # Retrieval and filtering happen inside one agentic loop; we surface both
    # as distinct stages for the frontend's stage view.
    _start_stage(db, podcast, Stage.RESEARCHING)
    t0 = time.perf_counter()
    outcome = SearchFilterAgent(llm).run(
        topic=topic,
        target_language=target,
        native_language=native,
        cefr_level=cefr,
    )
    if outcome.retrieved_count == 0:
        raise RuntimeError("No search results found for the topic.")
    _complete_stage(
        db,
        podcast,
        Stage.RESEARCHING,
        f"{outcome.retrieved_count} sources retrieved via MCP topic retrieval",
    )

    _start_stage(db, podcast, Stage.FILTERING)
    selected = outcome.selection.selected[:5]
    podcast.selected_sources = [s.model_dump() for s in selected]
    materials = outcome.materials
    _complete_stage(
        db, podcast, Stage.FILTERING, f"{len(selected)} sources selected"
    )
    _log_step(
        db,
        podcast,
        index=step_no,
        agent=SearchFilterAgent.name,
        stage=Stage.FILTERING,
        inputs={"topic": topic, "target_language": target, "cefr_level": cefr},
        output={
            "selected": [s.model_dump() for s in selected],
            "retrieved_count": outcome.retrieved_count,
        },
        detail=f"{outcome.retrieved_count} retrieved, {len(selected)} selected",
        duration_ms=int((time.perf_counter() - t0) * 1000),
    )
    step_no += 1

    content_adapter = ContentAdapterAgent(llm)
    scriptwriter = ScriptwriterAgent(llm)
    evaluator = EvaluatorAgent(llm)

    adapted = None
    script = None
    feedback_for_content: str | None = None
    feedback_for_script: str | None = None
    needs_review = False
    attempt = 0
    max_revisions = settings.max_revisions

    # --- Stages 3-5: adapt -> script -> evaluate (with bounded revisions) ---
    while True:
        if adapted is None or feedback_for_content is not None:
            _start_stage(db, podcast, Stage.ADAPTING)
            t0 = time.perf_counter()
            used_feedback = feedback_for_content
            adapted = content_adapter.run(
                topic=topic,
                target_language=target,
                native_language=native,
                cefr_level=cefr,
                materials=materials,
                feedback=feedback_for_content,
                owner=podcast.owner,
                learned_vocab_mcp=vocab_mcp,
            )
            podcast.adapted_content = adapted.model_dump()
            podcast.title = adapted.title
            _complete_stage(db, podcast, Stage.ADAPTING)
            _log_step(
                db,
                podcast,
                index=step_no,
                agent=content_adapter.name,
                stage=Stage.ADAPTING,
                iteration=attempt,
                inputs={"feedback": used_feedback, "materials_chars": len(materials)},
                output=adapted.model_dump(),
                duration_ms=int((time.perf_counter() - t0) * 1000),
            )
            step_no += 1
            feedback_for_content = None
            script = None  # content changed -> the script must be rewritten

        if script is None or feedback_for_script is not None:
            _start_stage(db, podcast, Stage.SCRIPTING)
            t0 = time.perf_counter()
            used_feedback = feedback_for_script
            script = scriptwriter.run(
                adapted=adapted,
                target_language=target,
                native_language=native,
                cefr_level=cefr,
                feedback=feedback_for_script,
                owner=podcast.owner,
                learned_vocab_mcp=vocab_mcp,
            )
            podcast.script = script.model_dump()
            if not podcast.title:
                podcast.title = script.title
            _complete_stage(db, podcast, Stage.SCRIPTING)
            _log_step(
                db,
                podcast,
                index=step_no,
                agent=scriptwriter.name,
                stage=Stage.SCRIPTING,
                iteration=attempt,
                inputs={"feedback": used_feedback},
                output=script.model_dump(),
                duration_ms=int((time.perf_counter() - t0) * 1000),
            )
            step_no += 1
            feedback_for_script = None

        _start_stage(db, podcast, Stage.EVALUATING)
        t0 = time.perf_counter()
        evaluation = evaluator.run(
            script=script,
            adapted=adapted,
            target_language=target,
            native_language=native,
            cefr_level=cefr,
        )
        db.add(
            Evaluation(
                podcast_id=podcast.id,
                iteration=attempt,
                passed=evaluation.passed,
                scores=evaluation.scores.model_dump(),
                overall_score=evaluation.overall_score,
                feedback=evaluation.feedback,
                revision_target=evaluation.revision_target,
                issues=evaluation.issues,
            )
        )
        passed = EvaluatorAgent.passes(evaluation)
        podcast.revision_count = attempt
        _complete_stage(
            db,
            podcast,
            Stage.EVALUATING,
            f"{'passed' if passed else 'needs revision'} "
            f"(overall {evaluation.overall_score:.1f}/5)",
        )
        _log_step(
            db,
            podcast,
            index=step_no,
            agent=evaluator.name,
            stage=Stage.EVALUATING,
            iteration=attempt,
            output=evaluation.model_dump(),
            detail=f"{'passed' if passed else 'needs revision'} "
            f"(overall {evaluation.overall_score:.1f}/5)",
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )
        step_no += 1

        if passed:
            break
        if attempt >= max_revisions:
            needs_review = True
            log.info(
                "podcast=%s revision limit (%d) reached; flagging needs_review",
                podcast.id,
                max_revisions,
            )
            break

        # Route the evaluator's feedback to the right agent for another pass.
        attempt += 1
        podcast.revision_count = attempt
        feedback = _format_feedback(evaluation.feedback, evaluation.issues)
        if evaluation.revision_target == "content_adapter":
            feedback_for_content = feedback
        else:
            feedback_for_script = feedback
        db.commit()

    # --- Stage 6: audio generation -----------------------------------------
    _start_stage(db, podcast, Stage.GENERATING_AUDIO)
    t0 = time.perf_counter()
    segments = _script_to_segments(
        script, target, native, immersion=is_immersion_level(cefr)
    )
    out_path = storage.audio_path(podcast.id, "wav")
    log.info(
        "podcast=%s synthesizing %d segment(s) via %s",
        podcast.id,
        len(segments),
        tts.name,
    )
    result = tts.synthesize(segments, out_path=out_path)
    podcast.audio_filename = os.path.basename(result.path)
    podcast.audio_format = result.format
    podcast.audio_duration_seconds = result.duration_seconds
    # Timestamped cues so the frontend can highlight/scroll the transcript in
    # sync with playback and seek by clicking text.
    podcast.transcript = _build_transcript(segments, result.timings)
    _complete_stage(
        db,
        podcast,
        Stage.GENERATING_AUDIO,
        f"{result.duration_seconds:.0f}s via {tts.name}, {len(podcast.transcript)} cues",
    )
    _log_step(
        db,
        podcast,
        index=step_no,
        agent=tts.name,
        stage=Stage.GENERATING_AUDIO,
        output={
            "segments": len(segments),
            "duration_seconds": result.duration_seconds,
            "format": result.format,
            "filename": podcast.audio_filename,
        },
        detail=f"{result.duration_seconds:.0f}s via {tts.name}",
        duration_ms=int((time.perf_counter() - t0) * 1000),
    )
    step_no += 1

    # --- Stage 7: interactive exercises (non-fatal) ------------------------
    # A bonus practice session; if it fails the podcast is still delivered.
    try:
        _start_stage(db, podcast, Stage.EXERCISES)
        t0 = time.perf_counter()
        exercises = ExerciseGeneratorAgent(llm).run(
            topic=topic,
            target_language=target,
            native_language=native,
            cefr_level=cefr,
            adapted=adapted,
        )
        podcast.exercises = exercises.model_dump()
        _complete_stage(db, podcast, Stage.EXERCISES, "5 exercises created")
        _log_step(
            db,
            podcast,
            index=step_no,
            agent=ExerciseGeneratorAgent.name,
            stage=Stage.EXERCISES,
            output=exercises.model_dump(),
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )
        step_no += 1
    except Exception as exc:  # noqa: BLE001 - exercises must never fail the podcast
        log.warning(
            "podcast=%s exercise generation failed (non-fatal): %s", podcast.id, exc
        )
        _append_event(podcast, Stage.EXERCISES, StageState.FAILED, str(exc)[:200])
        db.commit()

    # --- Record newly-taught vocabulary for spaced repetition --------------
    # Persist this episode's key vocabulary so future podcasts for this user
    # avoid repeating it. Bookkeeping only — never fail the podcast over it.
    try:
        recorded = record_terms(
            db,
            owner=podcast.owner,
            target_language=target,
            items=[(v.term, v.meaning) for v in adapted.key_vocabulary],
            podcast_id=podcast.id,
        )
        if recorded:
            log.info("podcast=%s recorded %d new learned word(s)", podcast.id, recorded)
    except Exception as exc:  # noqa: BLE001 - bookkeeping must not fail the podcast
        log.warning(
            "podcast=%s failed to record learned vocabulary: %s", podcast.id, exc
        )

    # --- Done --------------------------------------------------------------
    podcast.current_stage = Stage.DONE.value
    podcast.status = (
        PodcastStatus.NEEDS_REVIEW.value if needs_review else PodcastStatus.READY.value
    )
    _append_event(podcast, Stage.DONE, StageState.COMPLETED)
    db.commit()
    log.info("podcast=%s finished status=%s", podcast.id, podcast.status)
