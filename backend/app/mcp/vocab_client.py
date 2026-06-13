"""Synchronous facade over an MCP session to the learned-vocabulary server.

Mirrors ``TopicRetrievalMCP``: it spawns ``app.mcp.vocab_server`` as a stdio
subprocess, runs an asyncio loop on a dedicated thread, and exposes a plain
synchronous ``fetch_terms`` the agents can call. One session is opened per
podcast generation and shared by the Content Adapter and Scriptwriter agents.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import threading
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

try:
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    _MCP_IMPORT_ERROR: Exception | None = None
except Exception as exc:  # pragma: no cover - exercised only without mcp installed
    ClientSession = None  # type: ignore[assignment]
    _MCP_IMPORT_ERROR = exc

_BACKEND_DIR = Path(__file__).resolve().parents[2]


def _payload(result: Any) -> Any:
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured
    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            try:
                return json.loads(text)
            except (ValueError, TypeError):
                continue
    return {}


class LearnedVocabMCP:
    """Context manager owning an MCP session to the learned-vocabulary server."""

    def __init__(self, *, startup_timeout: float = 30.0, call_timeout: float = 30.0) -> None:
        self._startup_timeout = startup_timeout
        self._call_timeout = call_timeout
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._session: Any = None
        self._stop: asyncio.Event | None = None
        self._ready = threading.Event()
        self._startup_error: Exception | None = None

    # -- lifecycle ----------------------------------------------------------
    def open(self) -> "LearnedVocabMCP":
        if _MCP_IMPORT_ERROR is not None:
            raise RuntimeError(
                f"the 'mcp' package is not installed ({_MCP_IMPORT_ERROR})"
            )
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        if not self._ready.wait(self._startup_timeout):
            raise RuntimeError("learned-vocab MCP server did not become ready in time")
        if self._startup_error is not None:
            raise self._startup_error
        return self

    __enter__ = open

    def close(self) -> None:
        if self._loop is not None and self._stop is not None:
            self._loop.call_soon_threadsafe(self._stop.set)
        if self._thread is not None:
            self._thread.join(timeout=10)

    def __exit__(self, *exc_info: object) -> bool:
        self.close()
        return False

    def _run_loop(self) -> None:
        try:
            asyncio.run(self._serve())
        except Exception as exc:  # surfaced to open() via _startup_error
            self._startup_error = self._startup_error or exc
            self._ready.set()

    async def _serve(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._stop = asyncio.Event()
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "app.mcp.vocab_server"],
            env=os.environ.copy(),
            cwd=str(_BACKEND_DIR),
        )
        try:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    self._session = session
                    self._ready.set()
                    await self._stop.wait()
        except Exception as exc:
            self._startup_error = self._startup_error or exc
            self._ready.set()
            raise

    # -- query --------------------------------------------------------------
    def fetch_terms(
        self, *, owner: str, target_language: str, limit: int = 300
    ) -> list[str]:
        """Call get_learned_vocabulary and return the list of already-taught terms."""
        if self._loop is None or self._session is None:
            raise RuntimeError("learned-vocab MCP session is not running")
        coro = self._session.call_tool(
            "get_learned_vocabulary",
            {"owner": owner, "target_language": target_language, "limit": limit},
        )
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        payload = _payload(future.result(self._call_timeout))
        terms = payload.get("terms", []) if isinstance(payload, dict) else []
        return [t for t in terms if isinstance(t, str)]
