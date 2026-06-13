"""FastAPI application entry point for the Beshno backend."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import __version__
from .api.routes_podcasts import router
from .config import get_settings
from .database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

log = logging.getLogger("beshno")

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

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Log every unhandled error with a full traceback, then return a 500.

    Without this, an exception in an endpoint can surface to the client as a bare
    500 while leaving little in the server logs. We log method + path + traceback
    so failures are always diagnosable.
    """
    log.error(
        "Unhandled error on %s %s", request.method, request.url.path, exc_info=exc
    )
    return JSONResponse(
        status_code=500, content={"detail": "Internal server error"}
    )


app.include_router(router)


@app.get("/")
def root() -> dict:
    return {"name": "Beshno API", "version": __version__, "docs": "/docs"}
