"""
Direct WebIQ web-intelligence MCP access.

WebIQ (https://api.microsoft.ai) exposes a set of web-intelligence MCP tools —
``web`` (search), ``browse`` (open a URL), ``places`` (maps/POIs), ``news``,
``images``, ``videos``, ``finance``, ``sports`` and ``sonic``.

The file-based skills connect to WebIQ DIRECTLY via the Agent Framework
``MCPStreamableHTTPTool`` instead of going through the Foundry Toolbox's
``tool_search``/``call_tool`` discovery layer. The direct connection exposes the
real tools by name (so no discovery round-trip) and returns richer, more current
results. Auth is a static API key sent as a custom header (``x-apikey`` by
default), sourced from the Foundry ``webiq`` connection's CustomKeys and injected
into the container by Terraform.
"""

import logging

import httpx

from agent_framework import MCPStreamableHTTPTool
from config import config

logger = logging.getLogger("webiq")


def build_webiq_tool() -> MCPStreamableHTTPTool:
    """Create the (not-yet-connected) WebIQ MCP tool."""
    http_client = httpx.AsyncClient(
        headers={config.WEBIQ_API_KEY_HEADER: config.WEBIQ_API_KEY},
        timeout=120.0,
    )
    return MCPStreamableHTTPTool(
        name="webiq",
        url=config.WEBIQ_MCP_URL,
        http_client=http_client,
        load_prompts=False,
    )
