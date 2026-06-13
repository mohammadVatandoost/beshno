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

    # timed transcript cues are produced and aligned to the audio
    cues = podcast.transcript
    assert cues, "transcript cues should be produced"
    starts = [c["start"] for c in cues]
    assert starts == sorted(starts), "cues should be in non-decreasing start order"
    assert all(c["end"] <= podcast.audio_duration_seconds + 0.01 for c in cues)
    assert all(c["start"] <= c["end"] for c in cues)
    assert {"intro", "full", "segment", "explanation"} <= {c["kind"] for c in cues}

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

        assert body["durations"] == [5, 10, 20, 30]

        # invalid duration is rejected
        bad = client.post(
            "/api/podcasts",
            json={
                "native_language": "English",
                "target_language": "French",
                "cefr_level": "B1",
                "topic_description": "black holes",
                "duration_minutes": 7,
            },
        )
        assert bad.status_code == 422

        resp = client.post(
            "/api/podcasts",
            json={
                "native_language": "English",
                "target_language": "French",
                "cefr_level": "B1",
                "topic_category": "Science",
                "topic_description": "black holes",
                "duration_minutes": 20,
            },
        )
        assert resp.status_code == 201
        pid = resp.json()["id"]
        assert resp.json()["duration_minutes"] == 20

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


def test_learned_vocabulary_tracking():
    from sqlalchemy import select

    from app import vocabulary
    from app.database import SessionLocal, init_db
    from app.enums import PodcastStatus, Stage
    from app.models import Podcast, UserLearnedVocabulary
    from app.pipeline import generate_podcast

    init_db()

    db = SessionLocal()
    # A dedicated owner keeps this test isolated from vocab recorded by other
    # tests that share the same SQLite database.
    podcast = Podcast(
        owner="vocab_test_user",
        native_language="English",
        target_language="Spanish",
        cefr_level="A2",
        topic_category="Science",
        topic_description="rivers",
        status=PodcastStatus.PENDING.value,
        current_stage=Stage.QUEUED.value,
        stage_history=[],
    )
    db.add(podcast)
    db.commit()
    pid, owner = podcast.id, podcast.owner
    db.close()

    generate_podcast(pid)

    db = SessionLocal()
    rows = (
        db.execute(
            select(UserLearnedVocabulary).where(
                UserLearnedVocabulary.owner == owner,
                UserLearnedVocabulary.target_language == "Spanish",
            )
        )
        .scalars()
        .all()
    )
    assert rows, "key vocabulary should be recorded after generation"
    terms = {r.term for r in rows}
    assert "overview" in terms  # taught by the mock content adapter

    # The repository (what the MCP get_learned_vocabulary tool returns) reflects it.
    fetched = vocabulary.fetch_learned_terms(db, owner=owner, target_language="Spanish")
    assert "overview" in {f["term"] for f in fetched}

    # Recording is idempotent: existing words are skipped, only new ones added.
    added = vocabulary.record_terms(
        db,
        owner=owner,
        target_language="Spanish",
        items=[("overview", "dup"), ("brandnewword", "fresh")],
        podcast_id=pid,
    )
    assert added == 1

    # And vocabulary is scoped by target language (none recorded for French).
    fr = vocabulary.fetch_learned_terms(db, owner=owner, target_language="French")
    assert fr == []
    db.close()


def test_tone_selection():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        meta = client.get("/api/meta").json()
        tone_values = {t["value"] for t in meta["tones"]}
        assert {"auto", "nerdy", "professional", "friendly", "default"} <= tone_values
        assert all({"value", "label", "description"} <= set(t) for t in meta["tones"])

        # An explicit tone is used verbatim.
        r = client.post(
            "/api/podcasts",
            json={
                "native_language": "English",
                "target_language": "Spanish",
                "cefr_level": "A2",
                "topic_description": "the history of bread",
                "tone": "professional",
            },
        )
        assert r.status_code == 201
        detail = client.get(f"/api/podcasts/{r.json()['id']}").json()
        assert detail["tone"] == "professional"
        assert detail["resolved_tone"] == "professional"

        # "Auto" resolves to a concrete tone from the topic (mock heuristic).
        r2 = client.post(
            "/api/podcasts",
            json={
                "native_language": "English",
                "target_language": "Spanish",
                "cefr_level": "A2",
                "topic_category": "Technology",
                "topic_description": "quantum computing",
                "tone": "auto",
            },
        )
        assert r2.status_code == 201
        d2 = client.get(f"/api/podcasts/{r2.json()['id']}").json()
        assert d2["tone"] == "auto"
        assert d2["resolved_tone"] == "nerdy"  # tech topic -> nerdy
