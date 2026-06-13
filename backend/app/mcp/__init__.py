"""Model Context Protocol (MCP) integration.

Exposes the topic-retrieval (web search) API as an MCP server so the pipeline's
Search Filter agent can *call* it in an agentic loop, instead of having the
orchestrator pre-fetch results and stuff them into the prompt as context.

- ``topic_server`` — the stdio MCP server wrapping the configured SearchProvider.
- ``vocab_server`` — the stdio MCP server exposing the learned-vocabulary table.
- ``client`` / ``vocab_client`` — synchronous facades over MCP client sessions.
"""

from .client import TopicRetrievalMCP, mcp_unavailable
from .vocab_client import LearnedVocabMCP

__all__ = ["TopicRetrievalMCP", "LearnedVocabMCP", "mcp_unavailable"]
