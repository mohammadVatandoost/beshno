"""Background runner for the generation pipeline.

A podcast generation runs many sequential LLM + TTS calls and can take minutes,
so it must not run on the request-handling threadpool (that would tie up a
shared worker for the whole job). The API submits each job to a dedicated,
bounded ``ThreadPoolExecutor`` here and returns immediately.

Set ``PIPELINE_WORKERS`` to 0 (or less) for eager/synchronous execution — the
job runs inline on the caller's thread. Tests use this for determinism.
"""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor

from ..config import get_settings
from .orchestrator import generate_podcast

log = logging.getLogger(__name__)

_executor: ThreadPoolExecutor | None = None
_lock = threading.Lock()


def _get_executor(workers: int) -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        with _lock:
            if _executor is None:
                _executor = ThreadPoolExecutor(
                    max_workers=workers, thread_name_prefix="beshno-gen"
                )
                log.info("started generation worker pool (max_workers=%d)", workers)
    return _executor


def _run(podcast_id: str) -> None:
    try:
        generate_podcast(podcast_id)
    except Exception:  # generate_podcast records its own failures; this is a backstop
        log.exception("generation task crashed for podcast %s", podcast_id)


def submit_generation(podcast_id: str) -> None:
    """Queue a podcast for background generation (or run inline in eager mode)."""
    workers = get_settings().pipeline_workers
    if workers <= 0:
        log.info("podcast=%s generating synchronously (eager mode)", podcast_id)
        _run(podcast_id)
        return
    _get_executor(workers).submit(_run, podcast_id)
    log.info("podcast=%s queued for background generation", podcast_id)


def shutdown_generation(wait: bool = False) -> None:
    """Stop accepting new jobs on shutdown; in-flight jobs are left to finish."""
    global _executor
    if _executor is not None:
        _executor.shutdown(wait=wait)
        _executor = None
