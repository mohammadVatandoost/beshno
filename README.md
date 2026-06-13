# Beshno 🎧

**Beshno** is an AI-powered, personalized podcast generator for language learners.
You pick a topic and your languages; Beshno researches the topic, rewrites it to
your exact proficiency level (CEFR A1–C2), turns it into a two-person podcast, runs
a quality gate over it, and produces natural audio you can play in the browser.

Each podcast has two voices:

- **The learner (Mia)** speaks the **target language** at your CEFR level.
- **The teacher (Leo)** speaks your **native language**, explaining the grammar,
  vocabulary, idioms and culture in what Mia just said.

> Beshno runs **end-to-end with zero API keys** using built-in mock providers, so
> you can try the whole flow immediately. Add real keys to switch on Claude, Tavily
> and Google TTS.

---

## Features

- **Customisation** — predefined topic categories or a free-text topic; native
  language, target language and CEFR level (A1–C2).
- **Live generation status** — stage-level progress (Researching → Selecting
  sources → Adapting → Writing script → Reviewing → Generating audio).
- **Audio player** — play, pause, seek and download the generated episode.
- **Dashboard** — history of every podcast with languages, level, topic, timestamp
  and status (Ready / Needs review / Failed).
- **Transparency** — the transcript, adapted summary, key vocabulary, selected
  sources and the evaluator's quality scores are all shown.

---

## Architecture

```
                              ┌──────────────────────────────┐
   React + Vite (frontend) ── │  FastAPI (backend)            │
                              │                               │
   POST /api/podcasts ───────▶│  create record, run pipeline  │
   GET  /api/podcasts/:id ───▶│  in a background thread       │
                              └──────────────┬────────────────┘
                                             ▼
          [Search/Retrieval]  ─ Tavily (or mock), topic in target language
                  │
                  ▼
          Agent 1 · Search Filter      selects top 5 relevant, reliable sources
                  │
                  ▼
          Agent 2 · Content Adapter    rewrites to the CEFR level (≤ ~5 pages)
                  │
                  ▼
          Agent 3 · Scriptwriter       two-person dialogue (learner + teacher)
                  │
                  ▼
          Agent 4 · Evaluator          quality gate: CEFR fit, balance, teaching
                  │                     quality, factual accuracy, engagement
       fail ◀─────┤  (route feedback back to Agent 2 or 3, bounded retries)
                  │ pass
                  ▼
          [Text-to-Speech]  ─ Google Cloud TTS (or mock); distinct voices
                  │
                  ▼
          PostgreSQL + local file storage ──▶ Ready for playback
```

**Stack**

| Layer     | Tech                                                              |
| --------- | ----------------------------------------------------------------- |
| Frontend  | React 18, Vite, TypeScript, React Router                          |
| Backend   | FastAPI, SQLAlchemy 2, Pydantic v2                                |
| LLM       | Claude (Anthropic SDK), `claude-opus-4-8`, structured outputs     |
| Search    | Tavily                                                            |
| TTS       | Google Cloud Text-to-Speech (LINEAR16 → stitched WAV)             |
| Database  | PostgreSQL (SQLite supported for local dev)                       |
| Storage   | Local filesystem (`.wav`)                                         |

Every external dependency (LLM, search, TTS) sits behind a small provider
interface with a **mock implementation**, so the app always starts and the
pipeline always runs even with no credentials.

> 📐 For a deep dive into the six agents, the MCP-driven retrieval, the
> self-correcting evaluator loop and the full sequence diagrams, see
> **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

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
│       ├── agents/            # one file per agent
│       │   ├── search_filter.py     # Agent 1
│       │   ├── content_adapter.py   # Agent 2
│       │   ├── scriptwriter.py      # Agent 3
│       │   └── evaluator.py         # Agent 4
│       ├── providers/         # pluggable LLM / search / TTS (+ mocks)
│       │   ├── llm/  (claude.py, mock.py)
│       │   ├── search/ (tavily.py, mock.py)
│       │   └── tts/  (google.py, mock.py, wavutil.py)
│       ├── pipeline/
│       │   └── orchestrator.py      # runs all stages, retries, status updates
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

| Method   | Path                          | Description                              |
| -------- | ----------------------------- | ---------------------------------------- |
| `GET`    | `/api/meta`                   | Form options + active providers          |
| `POST`   | `/api/podcasts`               | Create a podcast and start generation    |
| `GET`    | `/api/podcasts`               | List all podcasts (newest first)         |
| `GET`    | `/api/podcasts/{id}`          | Full podcast detail (script, sources, …) |
| `GET`    | `/api/podcasts/{id}/status`   | Lightweight status for polling           |
| `GET`    | `/api/podcasts/{id}/audio`    | Stream/download the generated `.wav`     |
| `DELETE` | `/api/podcasts/{id}`          | Delete a podcast and its audio           |

Create payload:

```json
{
  "native_language": "English",
  "target_language": "Spanish",
  "cefr_level": "A2",
  "topic_category": "Science",
  "topic_description": "How volcanoes form"
}
```

Interactive docs at `/docs`.

---

## How generation works

1. **Retrieval** — the search provider fetches articles for the topic.
2. **Agent 1 · Search Filter** — selects the 5 most relevant, reliable sources.
3. **Agent 2 · Content Adapter** — rewrites the material into the target language,
   strictly at the chosen CEFR level (≤ ~5 pages), plus key points and vocabulary.
4. **Agent 3 · Scriptwriter** — turns it into a natural two-voice dialogue.
5. **Agent 4 · Evaluator** — scores CEFR compliance, language balance, pedagogical
   quality, factual accuracy and engagement. On a pass it proceeds; on a fail it
   routes structured feedback back to Agent 2 or Agent 3.
6. **Bounded retries** — after `MAX_REVISIONS` (default 2) cycles the best version
   is kept and flagged **Needs review** rather than looping forever.
7. **TTS** — the approved script is synthesised with a distinct voice per speaker
   and stored; the record is marked **Ready**.

Every evaluator verdict (scores, feedback, issues) is persisted to PostgreSQL for
transparency and tuning.

---

## Model benchmark

The pipeline was run end-to-end against two Claude models and graded by the
evaluator (overall quality, out of 5):

| Model           | Score   |
| --------------- | ------- |
| Claude Sonnet   | 4.7 / 5 |
| Claude Haiku    | 4.3 / 5 |

Sonnet produces higher-quality scripts; Haiku is faster and cheaper while still
clearing the quality gate. Set the model with `ANTHROPIC_MODEL`.

---

## Configuration reference

| Variable                         | Default                                   | Purpose                          |
| -------------------------------- | ----------------------------------------- | -------------------------------- |
| `DATABASE_URL`                   | `postgresql+psycopg://…@localhost:5433/…` | Database connection              |
| `ANTHROPIC_API_KEY`              | —                                         | Claude key (empty → mock LLM)    |
| `ANTHROPIC_MODEL`                | `claude-opus-4-8`                         | Claude model id                  |
| `LLM_PROVIDER`                   | `auto`                                    | `auto` \| `claude` \| `mock`     |
| `SEARCH_PROVIDER`                | `auto`                                    | `auto` \| `tavily` \| `mock`     |
| `TAVILY_API_KEY`                 | —                                         | Tavily key                       |
| `SEARCH_MAX_RESULTS`             | `10`                                      | Results fetched before filtering |
| `TTS_PROVIDER`                   | `auto`                                    | `auto` \| `google` \| `mock`     |
| `GOOGLE_API_KEY`                 | —                                         | Google API key for TTS (alternative to the JSON) |
| `GOOGLE_APPLICATION_CREDENTIALS` | —                                         | Path to Google service-account JSON |
| `MAX_REVISIONS`                  | `2`                                       | Evaluator revision cycles        |
| `AGENT_MAX_STEPS`                | `3`                                       | Agent tool-use loop step budget (≥2) |
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

- **Background work** uses FastAPI `BackgroundTasks` (a threadpool) — simple and
  in-process. For horizontal scaling or durability across restarts, move the
  pipeline to a task queue (Celery / RQ / Arq).
- **Schema bootstrap** uses `create_all` on startup. Add Alembic migrations before
  evolving the schema in production.
- **Auth** is not implemented; records use a single implicit `owner`. The column is
  in place so per-user auth can be layered on later.
- **Audio** is stored locally as WAV. Swap `storage.py` for object storage (S3/GCS)
  in production.
