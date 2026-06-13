"""Model Context Protocol (MCP) integration.

Exposes the topic-retrieval (web search) API as an MCP server so the pipeline's
Search Filter agent can *call* it in an agentic loop, instead of having the
orchestrator pre-fetch results and stuff them into the prompt as context.

- ``topic_server`` — the stdio MCP server wrapping the configured SearchProvider.
- ``client`` — a synchronous facade over an MCP client session for the pipeline.
"""

from .client import TopicRetrievalMCP, mcp_unavailable

__all__ = ["TopicRetrievalMCP", "mcp_unavailable"]
