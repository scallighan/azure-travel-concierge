"""
Concierge orchestration (Microsoft Agent Framework 1.12 — Agent Harness).

Lifecycle (created once at app startup):
  * FoundryChatClient            -> Azure AI Foundry chat model
  * Foundry Toolbox MCP tool     -> travel-concierge-toolbox (WebIQ + VIC), AAD-authed
  * Flights / Hotel / Food skills (sub-agents) exposed as supervisor tools
  * Payments agent               -> Foundry-hosted (portal-visible) or local fallback
  * CosmosHistoryProvider        -> per-itinerary chat memory (session_id keyed)
  * CosmosManager                -> named multi-itinerary + profile persistence

A harness supervisor is assembled per request so the user's profile and the
active itinerary id can be injected, reusing the already-connected tools and the
shared history provider. Conversation memory is scoped per (user_id, itinerary)
via the AgentSession session_id.
"""

import asyncio
import logging
from contextlib import AsyncExitStack

from azure.identity.aio import DefaultAzureCredential

from agent_framework import AgentSession, MCPStreamableHTTPTool, create_harness_agent
from agent_framework.foundry import FoundryChatClient
from agent_framework_azure_cosmos import CosmosHistoryProvider

import itinerary_tools
from config import config
from cosmos_manager import CosmosManager
from payments_agent import PaymentsAgent, payments_agent, set_payments
from prompts import PAYMENTS_AGENT_PROMPT, SUPERVISOR_PROMPT
from search_tool import search_visa_documentation
from specialists import build_specialist_tools
from toolbox import build_toolbox_tool, resolve_version

logger = logging.getLogger("concierge")


class Concierge:
    def __init__(self) -> None:
        self._stack = AsyncExitStack()
        self._credential: DefaultAzureCredential | None = None
        self._history_credential: DefaultAzureCredential | None = None
        self._client: FoundryChatClient | None = None
        self.cosmos: CosmosManager | None = None
        self._history: CosmosHistoryProvider | None = None
        self._payments = PaymentsAgent()
        self._toolbox_version: str | None = None
        self._tools: list = []

    def _payment_subagent(self, tool):
        return self._client.as_agent(
            name="payments_agent",
            instructions=PAYMENTS_AGENT_PROMPT,
            tools=[tool],
        ).as_tool(
            name="payments_agent",
            description="Secure checkout/purchase agent (VIC): confirm and complete purchases.",
            arg_name="query",
            arg_description="The purchase request, always including the user's id.",
        )

    async def start(self) -> None:
        self._credential = DefaultAzureCredential()
        self._client = FoundryChatClient(
            project_endpoint=config.PROJECT_ENDPOINT,
            model=config.MODEL_DEPLOYMENT,
            credential=self._credential,
        )

        # --- Foundry Toolbox (WebIQ + VIC) ---------------------------------
        toolbox_tool = None
        if config.toolbox_configured:
            try:
                self._toolbox_version = await asyncio.to_thread(resolve_version)
                toolbox_tool = await self._stack.enter_async_context(
                    build_toolbox_tool(self._toolbox_version)
                )
                logger.info("Connected Foundry Toolbox %s v%s",
                            config.FOUNDRY_TOOLBOX_NAME, self._toolbox_version)
            except Exception:
                logger.exception("Failed to connect Foundry Toolbox; falling back to web search.")
                toolbox_tool = None
                self._toolbox_version = None

        # --- specialist skills ---------------------------------------------
        if toolbox_tool is not None:
            skill_tools = [toolbox_tool]
        else:
            try:
                skill_tools = [self._client.get_web_search_tool()]
            except Exception:
                logger.warning("No web search tool available; skills will be limited.")
                skill_tools = []
        specialist_tools = build_specialist_tools(self._client, skill_tools=skill_tools)

        # --- payments: Foundry-hosted, else Toolbox/cart fallback ----------
        set_payments(self._payments)
        if self._toolbox_version:
            await self._payments.start(self._toolbox_version)

        if self._payments.enabled:
            payment_tool = payments_agent
        elif toolbox_tool is not None:
            payment_tool = self._payment_subagent(toolbox_tool)
        elif config.CART_MCP_URL:
            cart_tool = await self._stack.enter_async_context(
                MCPStreamableHTTPTool(name="cart_tools", url=config.CART_MCP_URL)
            )
            payment_tool = self._payment_subagent(cart_tool)
        else:
            payment_tool = None

        # --- per-itinerary chat memory -------------------------------------
        self._history_credential = DefaultAzureCredential()
        self._history = CosmosHistoryProvider(
            source_id="concierge",
            endpoint=config.COSMOS_ENDPOINT,
            database_name=config.COSMOS_DATABASE,
            container_name=config.COSMOS_HISTORY_CONTAINER,
            credential=self._history_credential,
        )

        self.cosmos = CosmosManager()
        itinerary_tools.set_cosmos(self.cosmos)

        self._tools = [
            *specialist_tools,
            *([payment_tool] if payment_tool else []),
            itinerary_tools.save_itinerary,
            search_visa_documentation,
        ]
        logger.info("Concierge started (payments_foundry=%s, toolbox=%s).",
                    self._payments.enabled, toolbox_tool is not None)

    async def stop(self) -> None:
        await self._stack.aclose()
        await self._payments.stop()
        if self._history:
            try:
                await self._history.close()
            except Exception:
                pass
        if self.cosmos:
            await self.cosmos.close()
        if self._client:
            await self._client.close()
        if self._credential:
            await self._credential.close()
        if self._history_credential:
            await self._history_credential.close()

    async def _user_profile_text(self, user_id: str) -> str:
        profile = await self.cosmos.get_user_profile(user_id) if self.cosmos else None
        parts = [f"User ID (use for all tool calls): {user_id}"]
        if profile:
            for key in ("name", "email", "address"):
                if profile.get(key):
                    parts.append(f"{key.title()}: {profile[key]}")
        return "; ".join(parts)

    async def _itinerary_context(self, user_id: str, itinerary_id: str) -> str:
        doc = await self.cosmos.get_itinerary(user_id, itinerary_id) if self.cosmos else None
        name = doc.get("name") if doc else "Untitled itinerary"
        return f'id="{itinerary_id}", name="{name}"'

    def _supervisor(self, instructions: str):
        return create_harness_agent(
            self._client,
            name="travel_concierge",
            agent_instructions=instructions,
            tools=self._tools,
            history_provider=self._history,
            disable_web_search=True,
            disable_file_memory=True,
        )

    async def clear_history(self, user_id: str, itinerary_id: str) -> None:
        if not self._history:
            return
        try:
            await self._history.clear(f"{user_id}:{itinerary_id}")
        except Exception:
            logger.warning("Failed to clear chat history for %s:%s", user_id, itinerary_id)

    async def stream(self, prompt: str, user_id: str, itinerary_id: str):
        """Yield text chunks for the supervisor's streamed response."""
        profile = await self._user_profile_text(user_id)
        itin_ctx = await self._itinerary_context(user_id, itinerary_id)
        agent = self._supervisor(
            SUPERVISOR_PROMPT.format(user_profile=profile, itinerary_context=itin_ctx)
        )
        session = AgentSession(session_id=f"{user_id}:{itinerary_id}")
        async for update in agent.run(prompt, stream=True, session=session):
            if getattr(update, "text", None):
                yield update.text
