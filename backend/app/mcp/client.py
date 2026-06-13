"""Synchronous facade over an MCP client session for the topic-retrieval server.

The pipeline runs synchronously in a background thread, but the MCP SDK is
async and talks to the server over stdio. This module hides that mismatch: it
spawns the server (``app.mcp.topic_server``) as a subprocess, runs an asyncio
event loop on a dedicated thread, and exposes plain synchronous methods
(``tool_schemas`` / ``call_tool``) that the agent's tool-use loop can drive.

As the agent calls ``search_topic`` (possibly several times with refined
queries), every result is cached in ``gathered`` keyed by URL, so the
orchestrator can build the adapter's source material from exactly what the
agent retrieved — no separate pre-fetch.
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

# Resolve gracefully if the optional `mcp` dependency is absent, so the service
# still imports; the failure surfaces only when MCP retrieval is actually used.
try:
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    _MCP_IMPORT_ERROR: Exception | None = None
except Exception as exc:  # pragma: no cover - exercised only without mcp installed
    ClientSession = None  # type: ignore[assignment]
    _MCP_IMPORT_ERROR = exc

# backend/ — the directory the server subprocess must run from so `app` imports.
_BACKEND_DIR = Path(__file__).resolve().parents[2]

# How much page content to show the model per result (full content is cached
# for the adapter; the model only needs an excerpt to judge relevance).
_EXCERPT_CHARS = 800


def mcp_unavailable() -> str | None:
    """Return a human-readable reason if MCP can't be used, else ``None``."""
    if _MCP_IMPORT_ERROR is not None:
        return f"the 'mcp' package is not installed ({_MCP_IMPORT_ERROR})"
    return None


class TopicRetrievalMCP:
    """Context manager owning an MCP session to the topic-retrieval server."""

    def __init__(self, *, startup_timeout: float = 30.0, call_timeout: float = 60.0) -> None:
        self._startup_timeout = startup_timeout
        self._call_timeout = call_timeout
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._session: Any = None
        self._stop: asyncio.Event | None = None
        self._ready = threading.Event()
        self._startup_error: Exception | None = None
        self._tools: list[Any] = []
        # url -> {"title", "url", "score", "content"} for every result retrieved.
        self.gathered: dict[str, dict] = {}

    # -- lifecycle ----------------------------------------------------------
    def __enter__(self) -> "TopicRetrievalMCP":
        reason = mcp_unavailable()
        if reason:
            raise RuntimeError(f"Cannot start MCP topic retrieval: {reason}")
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        if not self._ready.wait(self._startup_timeout):
            raise RuntimeError("MCP topic server did not become ready in time")
        if self._startup_error is not None:
            raise self._startup_error
        return self

    def __exit__(self, *exc_info: object) -> bool:
        if self._loop is not None and self._stop is not None:
            self._loop.call_soon_threadsafe(self._stop.set)
        if self._thread is not None:
            self._thread.join(timeout=10)
        return False

    def _run_loop(self) -> None:
        try:
            asyncio.run(self._serve())
        except Exception as exc:  # surfaced to __enter__ via _startup_error
            self._startup_error = self._startup_error or exc
            self._ready.set()

    async def _serve(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._stop = asyncio.Event()
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "app.mcp.topic_server"],
            env=os.environ.copy(),
            cwd=str(_BACKEND_DIR),
        )
        try:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    listing = await session.list_tools()
                    self._session = session
                    self._tools = list(listing.tools)
                    self._ready.set()
                    await self._stop.wait()
        except Exception as exc:
            self._startup_error = self._startup_error or exc
            self._ready.set()
            raise

    # -- tool interface -----------------------------------------------------
    def tool_schemas(self) -> list[dict]:
        """MCP tools as Anthropic tool definitions for ``messages.create``."""
        return [
            {
                "name": t.name,
                "description": t.description or "",
                "input_schema": t.inputSchema,
            }
            for t in self._tools
        ]

    def call_tool(self, name: str, arguments: dict | None = None) -> str:
        """Invoke an MCP tool synchronously; cache results, return model text."""
        if self._loop is None or self._session is None:
            raise RuntimeError("MCP session is not running")
        coro = self._session.call_tool(name, arguments or {})
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        result = future.result(self._call_timeout)
        return self._record_and_format(result)

    def _record_and_format(self, result: Any) -> str:
        payload = self._payload(result)
        results = payload.get("results", []) if isinstance(payload, dict) else []
        for item in results:
            url = item.get("url")
            if url:
                self.gathered[url] = item
        if not results:
            return "No results found. Try a different or broader query."
        lines = []
        for i, item in enumerate(results):
            content = (item.get("content") or "")[:_EXCERPT_CHARS]
            lines.append(
                f"[{i}] {item.get('title') or item.get('url')}\n"
                f"URL: {item.get('url')}\n"
                f"Search score: {item.get('score')}\n"
                f"Excerpt: {content}"
            )
        return "\n\n".join(lines)

    @staticmethod
    def _payload(result: Any) -> Any:
        """Extract the tool's JSON payload from a CallToolResult."""
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

    # -- materials ----------------------------------------------------------
    def materials_for(self, urls: list[str]) -> str:
        """Build the adapter's source material from the retrieved content."""
        parts = []
        for url in urls:
            item = self.gathered.get(url)
            if not item:
                continue
            parts.append(
                f"# {item.get('title') or url}\nURL: {url}\n{item.get('content') or ''}"
            )
        if parts:
            return "\n\n".join(parts)
        # Fallback: anything we retrieved, if the selected URLs didn't match.
        return "\n\n".join((item.get("content") or "") for item in list(self.gathered.values())[:5])
