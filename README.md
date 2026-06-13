# Beshno 🎧

**Beshno** is an AI-powered, personalized podcast generator for language learners.
You pick a topic, your languages, a runtime and a narrator tone; Beshno researches
the topic, rewrites it to your exact proficiency level (CEFR A1–C2), turns it into
a **two-phase** podcast, runs a self-correcting quality gate over it, produces
natural audio with a transcript that highlights in sync with playback, and hands
you an **interactive practice session** to test what you heard.

Each episode is built around two voices and plays in two phases:

- **The learner (Mia)** speaks the **target language** at your CEFR level.
- **The teacher (Leo)** speaks your **native language**, explaining the grammar,
  vocabulary, idioms and culture in what Mia just said.
- **Phase 1** plays the whole target-language piece; **Phase 2** replays it
  chunk-by-chunk with a breakdown after each chunk.

At B2+ Beshno switches to **full immersion** (100% target language). It also
remembers the vocabulary you've already been taught and avoids repeating it across
episodes (spaced repetition), and exposes per-run **generation analytics** (tokens,
latency and a cost estimate).

> Beshno runs **end-to-end with zero API keys** using built-in mock providers, so
> you can try the whole flow immediately. Add real keys to switch on Claude, Tavily
> and Google TTS.

---

## Features

- **Customisation** — predefined topic categories or a free-text topic; native
  language, target language, CEFR level (A1–C2), target runtime (5/10/20/30 min)
  and a **narrator tone** (auto, friendly, professional, nerdy, …).
- **Two-phase episodes** — a full target-language playback followed by a
  chunk-by-chunk breakdown; **full immersion** at B2+.
- **Synced transcript** — timed cues highlight and scroll the transcript with the
  audio (karaoke-style) and let you seek by clicking text.
- **Interactive practice** — every episode ships with 5 auto-generated exercises
  (speaking, vocabulary, reading MCQ), graded by an agent with a 1–10 score and
  per-item feedback.
- **Spaced-repetition memory** — Beshno tracks the words you've already learned
  per language and avoids re-introducing them in later episodes.
- **Live generation status** — stage-level progress (Researching → Selecting
  sources → Adapting → Writing script → Reviewing → Generating audio · Creating
  exercises).
- **Audio player** — play, pause, seek and download the generated episode.
- **Dashboard** — history of every podcast with languages, level, topic, timestamp
  and status (Ready / Needs review / Failed).
- **Transparency & analytics** — the transcript, adapted summary, key vocabulary,
  selected sources, the evaluator's quality scores, a per-step agent trace and a
  token/latency/cost breakdown are all shown.

---

## Architecture

```
                              ┌──────────────────────────────┐
   React + Vite (frontend) ── │  FastAPI (backend)            │
                              │                               │
   POST /api/podcasts ───────▶│  create record, 201 instantly │
   GET  /api/podcasts/:id ───▶│  job → worker pool (threads)  │
                              └──────────────┬────────────────┘
                                             ▼
          Tone Selector        picks a narrator persona (when tone=auto)
                  │
                  ▼
          Agent 1 · Search Filter      researches via MCP tool, picks top 5 sources
                  │                     ◀──▶ MCP Topic-Retrieval (Tavily / mock)
                  ▼
          Agent 2 · Content Adapter    rewrites to CEFR level + runtime budget
                  │                     ◀──▶ MCP Learned-Vocab (spaced repetition)
                  ▼
          Agent 3 · Scriptwriter       two-phase, two-voice episode
                  │
                  ▼
          Agent 4 · Evaluator          quality gate: CEFR fit, pedagogy,
                  │                     factual accuracy, engagement
       fail ◀─────┤  (route feedback back to Agent 2 or 3, bounded retries)
                  │ pass
                  ▼
            ┌─────┴───────────────────────┐   (run in parallel)
            ▼                             ▼
   [Text-to-Speech]               Agent 5 · Exercise Generator
   Google TTS (or mock);          5 practice exercises (non-fatal)
   distinct voices + timed cues
            │                             │
            └─────────────┬───────────────┘
                          ▼
          PostgreSQL + local file storage ──▶ Ready for playback

   Later · learner submits answers ─▶ Agent 6 · Exercise Grader (1–10 + feedback)
```

**Stack**

| Layer     | Tech                                                              |
| --------- | ----------------------------------------------------------------- |
| Frontend  | React 18, Vite, TypeScript, React Router                          |
| Backend   | FastAPI, SQLAlchemy 2, Pydantic v2                                |
| LLM       | Claude (Anthropic SDK), `claude-opus-4-8`, structured outputs + model-aware extended thinking |
| Retrieval | MCP topic-retrieval server over Tavily (or mock)                 |
| Memory    | MCP learned-vocabulary server (spaced repetition) over PostgreSQL |
| TTS       | Google Cloud Text-to-Speech (LINEAR16 → stitched WAV) + timed transcript cues |
| Database  | PostgreSQL (SQLite supported for local dev)                       |
| Storage   | Local filesystem (`.wav`)                                         |

Every external dependency (LLM, search, TTS) sits behind a small provider
interface with a **mock implementation**, so the app always starts and the
pipeline always runs even with no credentials.

> 📐 For a deep dive into the six agents + tone selector, the two MCP servers, the
> self-correcting evaluator loop, the parallel finalize step and the full sequence
> diagrams, see **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

---

## Repository layout

```
beshno/
├── backend/
│   └── app/
│       ├── main.py            # FastAPI app + lifespan (creates tables)
│       ├── config.py          # env-driven settings + provider resolution
│       ├── database.py        # SQLAlchemy engine / session / Base
│       ├── models.py          # Podcast + Evaluation ORM models
│       ├── schemas.py         # API request/response models
│       ├── content_models.py  # shared domain models (also agent output schemas)
│       ├── enums.py           # status / stage / CEFR enums
│       ├── languages.py       # language list + BCP-47 mapping for TTS
│       ├── storage.py         # local audio storage
│       ├── telemetry.py       # per-run token / latency / cost recorder
│       ├── agents/            # one file per agent (base.py = shared base)
│       │   ├── base.py                # shared Agent base (LLM + vocab helper)
│       │   ├── tone_selector.py       # aux · picks narrator persona (tone=auto)
│       │   ├── search_filter.py       # Agent 1
│       │   ├── content_adapter.py     # Agent 2
│       │   ├── scriptwriter.py        # Agent 3
│       │   ├── evaluator.py           # Agent 4
│       │   ├── exercise_generator.py  # Agent 5
│       │   └── exercise_grader.py     # Agent 6 (on submit)
│       ├── mcp/               # Model Context Protocol servers + client facades
│       │   ├── topic_server.py / client.py        # agentic web retrieval
│       │   └── vocab_server.py / vocab_client.py   # spaced-repetition memory
│       ├── providers/         # pluggable LLM / search / TTS (+ mocks)
│       │   ├── llm/  (claude.py, mock.py)
│       │   ├── search/ (tavily.py, mock.py)
│       │   └── tts/  (google.py, mock.py, wavutil.py)
│       ├── pipeline/
│       │   ├── runner.py              # worker pool: dispatch generation off-thread
│       │   └── orchestrator.py        # stages, retries, parallel finalize, status
│       └── api/
│           └── routes_podcasts.py
│   └── tests/                 # end-to-end pipeline + API tests (mock providers)
└── frontend/
    └── src/
        ├── pages/   (DashboardPage, CreatePage, DetailPage)
        ├── components/ (GenerationStatus, AudioPlayer, ScriptView, StatusBadge)
        ├── hooks/usePodcast.ts        # polls status until terminal
        └── api/client.ts
```

---

## Quickstart — Docker (no keys needed)

Runs Postgres, the backend and the frontend. With no keys set it uses mock
providers, so generation completes in seconds and produces a (silent) audio file.

```bash
docker compose up --build
```

- Frontend: <http://localhost:3000>
- Backend API + docs: <http://localhost:8000/docs>

To switch on real providers, export keys before `docker compose up` (or put them
in a root `.env`):

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export TAVILY_API_KEY=tvly-...
# Google TTS in Docker: mount the JSON (see the commented volume in
# docker-compose.yml) and set GOOGLE_APPLICATION_CREDENTIALS=/secrets/gcp.json
docker compose up --build
```

---

## Quickstart — local development

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # or: uv venv && source .venv/bin/activate
pip install -r requirements.txt                     # or: uv pip install -r requirements.txt
cp .env.example .env                                 # optional; defaults run on mocks

# Use SQLite for a zero-dependency run (edit .env):
#   DATABASE_URL=sqlite:///./beshno.db
# Or start Postgres only:
#   docker compose up -d db

uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173 (proxies /api to :8000)
```

Open <http://localhost:5173>, click **New podcast**, and create one.

---

## Enabling real providers

| Provider            | Env var(s)                                       | Notes |
| ------------------- | ------------------------------------------------ | ----- |
| **Claude (LLM)**    | `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`           | Default model `claude-opus-4-8`. Uses structured outputs + adaptive thinking. |
| **Tavily (search)** | `TAVILY_API_KEY`                                 | Topic research. |
| **Google TTS**      | `GOOGLE_API_KEY` **or** `GOOGLE_APPLICATION_CREDENTIALS` | An API key with the Text-to-Speech API enabled, or a service-account JSON path (ADC). |

Provider selection is `auto` by default: each provider is used when its
credential is present, otherwise the mock is used. Force a provider with
`LLM_PROVIDER`, `SEARCH_PROVIDER`, `TTS_PROVIDER` (`auto` | real | `mock`).
The active providers are logged on startup and returned by `GET /api/meta`.

---

## API reference

| Method   | Path                                    | Description                              |
| -------- | --------------------------------------- | ---------------------------------------- |
| `GET`    | `/api/meta`                             | Form options (tones, durations, …) + active providers |
| `POST`   | `/api/podcasts`                         | Create a podcast and start generation    |
| `GET`    | `/api/podcasts`                         | List all podcasts (newest first)         |
| `GET`    | `/api/podcasts/{id}`                    | Full podcast detail (script, sources, exercises, analytics) |
| `GET`    | `/api/podcasts/{id}/status`             | Lightweight status for polling           |
| `GET`    | `/api/podcasts/{id}/steps`              | Per-agent trace (inputs, output, duration, tokens) |
| `POST`   | `/api/podcasts/{id}/exercises/submit`   | Submit answers → graded score + feedback |
| `GET`    | `/api/podcasts/{id}/audio`              | Stream/download the generated `.wav`     |
| `DELETE` | `/api/podcasts/{id}`                    | Delete a podcast and its audio           |

Create payload (`duration_minutes` ∈ {5, 10, 20, 30}; `tone` ∈ {auto, default,
professional, friendly, candid, quirky, efficient, nerdy, cynical}):

```json
{
  "native_language": "English",
  "target_language": "Spanish",
  "cefr_level": "A2",
  "topic_category": "Science",
  "topic_description": "How volcanoes form",
  "duration_minutes": 10,
  "tone": "auto"
}
```

Interactive docs at `/docs`.

---

## How generation works

A `POST /api/podcasts` returns `201` instantly with a tracking id; the job is
dispatched to a worker pool (`PIPELINE_WORKERS` threads) and runs off the request
thread while the frontend polls stage-level progress.

0. **Tone Selector** — when `tone=auto`, picks a narrator persona from the topic;
   the resolved tone then steers Agents 2 and 3.
1. **Agent 1 · Search Filter** — given the `search_topic` MCP tool, researches the
   topic agentically (possibly several refined queries) and selects the 5 best
   sources.
2. **Agent 2 · Content Adapter** — rewrites the material into the target language
   at the chosen CEFR level and runtime budget, plus key points and vocabulary. It
   queries the learned-vocab MCP to avoid words you already know.
3. **Agent 3 · Scriptwriter** — turns it into a two-phase, two-voice episode
   (full playback + chunk-by-chunk breakdown).
4. **Agent 4 · Evaluator** — scores CEFR compliance, pedagogical quality, factual
   accuracy and engagement (0–5 each). It passes only when its own verdict **and**
   the score thresholds agree; on a fail it routes structured feedback back to
   Agent 2 or Agent 3.
5. **Bounded retries** — after `MAX_REVISIONS` (default 2) cycles the best version
   is kept and flagged **Needs review** rather than looping forever.
6. **Parallel finalize** — once the script passes, TTS (distinct voice per speaker
   + timed transcript cues) and **Agent 5 · Exercise Generator** run concurrently.
   Audio is required; exercises are a bonus (a failure is logged, the podcast still
   ships). The record is marked **Ready** and the new vocabulary is recorded for
   spaced repetition.
7. **Practice (on demand)** — when the learner submits answers,
   **Agent 6 · Exercise Grader** returns a 1–10 score with per-item feedback.

Every step is persisted: evaluator verdicts (scores, feedback, target), a
per-agent trace (`AgentStep`: inputs, output, duration, token usage) and per-run
telemetry (total tokens, LLM calls, wall-clock time and a cost estimate).

---

## Configuration reference

| Variable                         | Default                                   | Purpose                          |
| -------------------------------- | ----------------------------------------- | -------------------------------- |
| `DATABASE_URL`                   | `postgresql+psycopg://…@localhost:5433/…` | Database connection              |
| `ANTHROPIC_API_KEY`              | —                                         | Claude key (empty → mock LLM)    |
| `ANTHROPIC_MODEL`                | `claude-opus-4-8`                         | Claude model id                  |
| `ANTHROPIC_THINKING`             | `adaptive`                                | Extended-thinking mode: `adaptive` \| `off` \| `enabled[:budget]` |
| `LLM_PROVIDER`                   | `auto`                                    | `auto` \| `claude` \| `mock`     |
| `SEARCH_PROVIDER`                | `auto`                                    | `auto` \| `tavily` \| `mock`     |
| `TAVILY_API_KEY`                 | —                                         | Tavily key                       |
| `SEARCH_MAX_RESULTS`             | `10`                                      | Results fetched before filtering |
| `TTS_PROVIDER`                   | `auto`                                    | `auto` \| `google` \| `mock`     |
| `GOOGLE_API_KEY`                 | —                                         | Google API key for TTS (alternative to the JSON) |
| `GOOGLE_APPLICATION_CREDENTIALS` | —                                         | Path to Google service-account JSON |
| `MAX_REVISIONS`                  | `2`                                       | Evaluator revision cycles        |
| `AGENT_MAX_STEPS`                | `3`                                       | Agent tool-use loop step budget (≥2) |
| `PIPELINE_WORKERS`               | `4`                                       | Generation worker threads (`0` = inline/synchronous) |
| `STORAGE_DIR`                    | `./storage`                               | Where audio files are written    |
| `CORS_ORIGINS`                   | `http://localhost:5173,…:3000`            | Allowed frontend origins         |

---

## Tests

The backend has end-to-end pipeline and API tests that run entirely on mock
providers (SQLite, no network):

```bash
cd backend
pip install -r requirements-dev.txt
pytest -q
```

Frontend type-check / build:

```bash
cd frontend
npm run typecheck
npm run build
```

---

## Notes & production considerations

- **Background work** uses an in-process worker pool (`ThreadPoolExecutor`,
  `PIPELINE_WORKERS`) drained on shutdown — simple and in-process. For horizontal
  scaling or durability across restarts, move the pipeline to a task queue
  (Celery / RQ / Arq).
- **Schema** is managed by **Alembic**: on startup the real (PostgreSQL) database
  is migrated to head, while SQLite dev runs fall back to `create_all`. New columns
  ship as versioned migrations under `backend/alembic/versions/`.
- **Auth** is not implemented; records use a single implicit `owner`. The column is
  in place so per-user auth can be layered on later.
- **Audio** is stored locally as WAV. Swap `storage.py` for object storage (S3/GCS)
  in production.
