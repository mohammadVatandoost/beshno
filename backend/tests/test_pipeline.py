"""End-to-end pipeline and API tests running entirely on mock providers."""

import os


def test_full_pipeline_with_mocks():
    from app.database import SessionLocal, init_db
    from app.enums import PodcastStatus, Stage
    from app.models import Podcast
    from app.pipeline import generate_podcast
    from app.storage import Storage

    init_db()

    db = SessionLocal()
    podcast = Podcast(
        native_language="English",
        target_language="Spanish",
        cefr_level="A2",
        topic_category="Science",
        topic_description="space travel",
        status=PodcastStatus.PENDING.value,
        current_stage=Stage.QUEUED.value,
        stage_history=[],
    )
    db.add(podcast)
    db.commit()
    pid = podcast.id
    db.close()

    generate_podcast(pid)

    db = SessionLocal()
    podcast = db.get(Podcast, pid)
    assert podcast.status in (PodcastStatus.READY.value, PodcastStatus.NEEDS_REVIEW.value)
    assert podcast.current_stage == Stage.DONE.value
    assert podcast.selected_sources, "sources should be selected"
    assert podcast.adapted_content is not None
    assert podcast.script is not None and podcast.script["segments"]
    assert podcast.audio_filename
    assert podcast.audio_duration_seconds and podcast.audio_duration_seconds > 0
    assert len(podcast.evaluations) >= 1

    # agent steps are logged per session for step-by-step review
    steps = sorted(podcast.agent_steps, key=lambda s: s.step_index)
    assert steps, "agent steps should be logged"
    agents_seen = [s.agent for s in steps]
    for expected in ("search_filter", "content_adapter", "scriptwriter", "evaluator"):
        assert expected in agents_seen, f"missing logged step for {expected}"
    # step indices are contiguous and ordered
    assert [s.step_index for s in steps] == list(range(len(steps)))
    assert all(s.podcast_id == pid for s in steps)
    # stage history should record every stage as completed
    completed = {e["stage"] for e in podcast.stage_history if e["state"] == "completed"}
    for stage in ("researching", "filtering", "adapting", "scripting", "evaluating", "generating_audio"):
        assert stage in completed, f"missing completed stage {stage}"

    audio_path = Storage().audio_path(pid, podcast.audio_format)
    assert os.path.exists(audio_path)
    assert os.path.getsize(audio_path) > 44  # bigger than a bare WAV header
    db.close()


def test_api_create_status_and_audio():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        meta = client.get("/api/meta")
        assert meta.status_code == 200
        body = meta.json()
        assert body["cefr_levels"] == ["A1", "A2", "B1", "B2", "C1", "C2"]
        assert body["providers"]["llm"] == "mock"

        resp = client.post(
            "/api/podcasts",
            json={
                "native_language": "English",
                "target_language": "French",
                "cefr_level": "B1",
                "topic_category": "Science",
                "topic_description": "black holes",
            },
        )
        assert resp.status_code == 201
        pid = resp.json()["id"]

        # BackgroundTasks run synchronously within the TestClient request.
        status = client.get(f"/api/podcasts/{pid}/status")
        assert status.status_code == 200
        assert status.json()["status"] in ("ready", "needs_review")

        detail = client.get(f"/api/podcasts/{pid}")
        assert detail.status_code == 200
        assert detail.json()["script"]["segments"]
        assert detail.json()["has_audio"] is True

        audio = client.get(f"/api/podcasts/{pid}/audio")
        assert audio.status_code == 200
        assert audio.headers["content-type"].startswith("audio/")

        listing = client.get("/api/podcasts")
        assert listing.status_code == 200
        assert any(p["id"] == pid for p in listing.json())

        steps = client.get(f"/api/podcasts/{pid}/steps")
        assert steps.status_code == 200
        body = steps.json()
        assert body, "steps endpoint should return logged agent steps"
        assert body[0]["step_index"] == 0
        assert {"search_filter", "scriptwriter"} <= {s["agent"] for s in body}


def test_immersion_for_advanced_levels():
    """B2+ episodes must be 100% target language (no native explanation runs)."""
    from app.content_models import PodcastScript
    from app.database import SessionLocal, init_db
    from app.enums import PodcastStatus, Stage
    from app.models import Podcast
    from app.pipeline import generate_podcast
    from app.pipeline.orchestrator import _script_to_segments

    init_db()

    db = SessionLocal()
    podcast = Podcast(
        native_language="English",
        target_language="Spanish",
        cefr_level="C1",
        topic_category="Science",
        topic_description="black holes",
        status=PodcastStatus.PENDING.value,
        current_stage=Stage.QUEUED.value,
        stage_history=[],
    )
    db.add(podcast)
    db.commit()
    pid = podcast.id
    db.close()

    generate_podcast(pid)

    db = SessionLocal()
    podcast = db.get(Podcast, pid)
    assert podcast.status in (
        PodcastStatus.READY.value,
        PodcastStatus.NEEDS_REVIEW.value,
    )
    assert podcast.script and podcast.script["segments"]
    # Immersion: every explanation run must be in the target language.
    for seg in podcast.script["segments"]:
        for run in seg["native_explanation"]:
            assert run["lang"] == "target", "immersion must omit the native language"

    # The audio track is entirely the target locale (no native-locale segments).
    script = PodcastScript(**podcast.script)
    segs = _script_to_segments(script, "Spanish", "English", immersion=True)
    assert segs and all(s.language_code == "es-ES" for s in segs)
    db.close()


def test_exercises_generated_and_graded():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        resp = client.post(
            "/api/podcasts",
            json={
                "native_language": "English",
                "target_language": "Spanish",
                "cefr_level": "A2",
                "topic_category": "Science",
                "topic_description": "volcanoes",
            },
        )
        assert resp.status_code == 201
        pid = resp.json()["id"]

        detail = client.get(f"/api/podcasts/{pid}").json()
        assert detail["has_exercises"] is True
        ex = detail["exercises"]
        assert ex and "prompt" in ex["speaking"]
        assert len(ex["vocabulary"]) == 2
        assert len(ex["reading"]) == 2
        # Answer keys must NOT be exposed to the client before grading.
        assert "answer" not in ex["vocabulary"][0]
        assert "correct_index" not in ex["reading"][0]
        assert "options" in ex["reading"][0]

        submission = {
            "speaking_answer": "Volcanoes form when magma rises to the surface.",
            "vocabulary_answers": [ex["vocabulary"][0]["term"], "no idea"],
            "reading_answers": [0, 1],
        }
        graded = client.post(
            f"/api/podcasts/{pid}/exercises/submit", json=submission
        )
        assert graded.status_code == 200
        g = graded.json()
        assert 1 <= g["score"] <= 10
        assert g["feedback"]
        assert len(g["items"]) == 5
        assert len(g["reading_correct_index"]) == 2
        assert len(g["vocabulary_reference"]) == 2
