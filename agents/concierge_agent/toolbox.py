"""
Foundry Toolbox access.

The ``travel-concierge-toolbox`` bundles WebIQ (web intelligence) and the VIC
payment tools behind a single MCP-compatible endpoint. It is consumed via the
Agent Framework ``MCPStreamableHTTPTool`` using an AAD bearer token (centralized
Toolbox auth), following the Foundry Toolbox usage pattern.
"""

import logging

import httpx
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

from agent_framework import MCPStreamableHTTPTool
from config import config

logger = logging.getLogger("toolbox")

_TOKEN_SCOPE = "https://ai.azure.com/.default"


class _ToolboxAuth(httpx.Auth):
    """Injects a fresh bearer token on every request to the Toolbox endpoint."""

    def __init__(self, token_provider):
        self._get_token = token_provider

    def auth_flow(self, request):
        request.headers["Authorization"] = f"Bearer {self._get_token()}"
        yield request


def resolve_version(credential=None) -> str:
    """Return the configured Toolbox version, else the toolbox's default version."""
    if config.FOUNDRY_TOOLBOX_VERSION:
        return config.FOUNDRY_TOOLBOX_VERSION
    from azure.ai.projects import AIProjectClient

    own_cred = credential is None
    credential = credential or DefaultAzureCredential()
    try:
        with AIProjectClient(
            endpoint=config.PROJECT_ENDPOINT, credential=credential, allow_preview=True
        ) as project:
            tb = project.toolboxes.get(config.FOUNDRY_TOOLBOX_NAME)
            return getattr(tb, "default_version", None) or getattr(tb, "version", "") or ""
    finally:
        if own_cred:
            credential.close()


def toolbox_url(version: str) -> str:
    endpoint = config.PROJECT_ENDPOINT.rstrip("/")
    return f"{endpoint}/toolboxes/{config.FOUNDRY_TOOLBOX_NAME}/versions/{version}/mcp?api-version=v1"


def build_toolbox_tool(version: str) -> MCPStreamableHTTPTool:
    """Create the (not-yet-connected) Toolbox MCP tool for the given version."""
    token_provider = get_bearer_token_provider(DefaultAzureCredential(), _TOKEN_SCOPE)
    http_client = httpx.AsyncClient(
        auth=_ToolboxAuth(token_provider),
        headers={"Foundry-Features": "Toolboxes=V1Preview"},
        timeout=120.0,
    )
    return MCPStreamableHTTPTool(
        name=config.FOUNDRY_TOOLBOX_NAME,
        url=toolbox_url(version),
        http_client=http_client,
        load_prompts=False,
    )
