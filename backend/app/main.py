"""FastAPI application entry point for the Beshno backend."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .api.routes_podcasts import router
from .config import get_settings
from .database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    log = logging.getLogger("beshno")
    providers = {
        "llm": settings.resolved_llm_provider(),
        "search": settings.resolved_search_provider(),
        "tts": settings.resolved_tts_provider(),
    }
    log.info(
        "Beshno started. providers: llm=%s search=%s tts=%s",
        providers["llm"],
        providers["search"],
        providers["tts"],
    )
    mocks = [name for name, value in providers.items() if value == "mock"]
    if mocks:
        log.warning(
            "MOCK providers active for: %s. Output is placeholder "
            "(mock LLM = templated scripts, mock TTS = SILENT audio). "
            "Set ANTHROPIC_API_KEY / TAVILY_API_KEY / GOOGLE_API_KEY to enable real providers.",
            ", ".join(mocks),
        )
    yield


app = FastAPI(title="Beshno API", version=__version__, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root() -> dict:
    return {"name": "Beshno API", "version": __version__, "docs": "/docs"}
