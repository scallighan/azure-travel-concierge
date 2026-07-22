"""
Foundry-hosted Payments agent.

Registers a persisted, versioned agent in the Azure AI Foundry project (so it is
visible/governable in the Foundry portal) whose tools come from the
``travel-concierge-toolbox`` Foundry Toolbox (VIC payment tools). The harness
supervisor invokes it as a regular tool; execution happens inside Foundry via
the ``agent_reference`` responses API.

If the Foundry project/Toolbox is not configured or registration fails, ``start``
is a no-op and the concierge falls back to a local, Toolbox-backed sub-agent.
"""

import asyncio
import logging
from typing import Annotated

from azure.identity import DefaultAzureCredential
from pydantic import Field

from config import config
from prompts import PAYMENTS_AGENT_PROMPT
from toolbox import toolbox_url

logger = logging.getLogger("payments-agent")

_instance: "PaymentsAgent | None" = None


class PaymentsAgent:
    def __init__(self) -> None:
        self._credential = None
        self._project = None
        self._openai = None
        self.agent_name: str | None = None
        self.agent_version: str | None = None

    @property
    def enabled(self) -> bool:
        return self.agent_name is not None

    def _vic_tool(self):
        """Direct MCP tool for the mock VIC payment service.

        Points at the ``vic-mock`` Foundry connection so all payment traffic
        flows through the mock VIC MCP server (not the shared Toolbox).
        """
        from azure.ai.projects.models import MCPTool

        server_url = config.VIC_MCP_URL
        if not server_url:
            conn = self._project.connections.get(config.VIC_MCP_CONNECTION)
            server_url = getattr(conn, "target", None)
        if not server_url:
            raise RuntimeError(
                f"Could not resolve MCP URL for connection '{config.VIC_MCP_CONNECTION}'."
            )

        return MCPTool(
            server_label="vic_mock",
            server_url=server_url,
            project_connection_id=config.VIC_MCP_CONNECTION,
            require_approval="never",
        )

    def _register(self) -> None:
        """Synchronous Foundry registration (run in a worker thread)."""
        from azure.ai.projects import AIProjectClient
        from azure.ai.projects.models import PromptAgentDefinition

        self._credential = DefaultAzureCredential()
        self._project = AIProjectClient(
            endpoint=config.PROJECT_ENDPOINT,
            credential=self._credential,
            allow_preview=True,
        )
        self._openai = self._project.get_openai_client()

        agent = self._project.agents.create_version(
            agent_name=config.PAYMENTS_AGENT_NAME,
            definition=PromptAgentDefinition(
                model=config.MODEL_DEPLOYMENT,
                instructions=PAYMENTS_AGENT_PROMPT,
                tools=[self._vic_tool()],
            ),
        )
        self.agent_name = agent.name
        self.agent_version = agent.version
        logger.info("Foundry payments agent registered: %s v%s", agent.name, agent.version)

    async def start(self) -> None:
        if not config.PROJECT_ENDPOINT:
            logger.warning("Foundry payments agent not started (PROJECT_ENDPOINT not set).")
            return
        try:
            await asyncio.to_thread(self._register)
        except Exception:  # pragma: no cover
            logger.exception("Failed to register Foundry payments agent; falling back to local.")
            self.agent_name = None

    async def stop(self) -> None:
        if self._project is not None:
            await asyncio.to_thread(self._project.close)
        if self._credential is not None:
            await asyncio.to_thread(self._credential.close)

    def _invoke_sync(self, prompt: str) -> str:
        response = self._openai.responses.create(
            input=prompt,
            extra_body={"agent_reference": {"name": self.agent_name, "type": "agent_reference"}},
        )
        return getattr(response, "output_text", "") or ""

    async def invoke(self, query: str, user_id: str) -> str:
        prompt = f"user_id: {user_id}\n\n{query}"
        try:
            return await asyncio.to_thread(self._invoke_sync, prompt)
        except Exception as exc:  # pragma: no cover
            logger.exception("Payments agent invocation failed")
            return f"Payment processing is unavailable right now: {exc}"


def set_payments(agent: PaymentsAgent) -> None:
    global _instance
    _instance = agent


async def payments_agent(
    query: Annotated[str, Field(description="The purchase/checkout request in natural language.")],
    user_id: Annotated[str, Field(description="The user's unique id.")],
) -> str:
    """Delegate a confirmed purchase or checkout step to the secure Foundry payments agent (VIC)."""
    if _instance is None or not _instance.enabled:
        return "Payments agent is not available."
    return await _instance.invoke(query, user_id)
