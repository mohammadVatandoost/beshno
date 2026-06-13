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
    log.info(
        "Beshno started. providers: llm=%s search=%s tts=%s",
        settings.resolved_llm_provider(),
        settings.resolved_search_provider(),
        settings.resolved_tts_provider(),
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
