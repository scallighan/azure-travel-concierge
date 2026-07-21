"""
Concierge orchestration wiring (Microsoft Agent Framework, v1.11 API).

Lifecycle (created once at app startup):
  * FoundryChatClient        -> Azure AI Foundry chat model
  * MCPStreamableHTTPTool x2 -> travel + cart MCP servers (kept connected)
  * travel_assistant / cart_manager sub-agents -> exposed to the supervisor as tools
  * CosmosManager            -> itinerary + profile persistence

A fresh supervisor Agent is built per request so the user's profile/id can be
injected into its instructions, reusing the already-connected tools. Conversation
memory is kept per (user_id, session_id) via AgentSession.
"""

import logging
from contextlib import AsyncExitStack

from azure.identity.aio import DefaultAzureCredential

from agent_framework import Agent, AgentSession, MCPStreamableHTTPTool
from agent_framework.foundry import FoundryChatClient

import itinerary_tools
from config import config
from cosmos_manager import CosmosManager
from prompts import CART_AGENT_PROMPT, SUPERVISOR_PROMPT, TRAVEL_AGENT_PROMPT
from search_tool import search_visa_documentation

logger = logging.getLogger("concierge")


class Concierge:
    def __init__(self) -> None:
        self._stack = AsyncExitStack()
        self._credential: DefaultAzureCredential | None = None
        self._client: FoundryChatClient | None = None
        self.cosmos: CosmosManager | None = None
        self._travel_tool = None
        self._cart_tool = None
        self._sessions: dict[str, AgentSession] = {}

    async def start(self) -> None:
        self._credential = DefaultAzureCredential()
        self._client = FoundryChatClient(
            project_endpoint=config.PROJECT_ENDPOINT,
            model=config.MODEL_DEPLOYMENT,
            credential=self._credential,
        )

        # Connect the MCP servers and keep the sessions open for the app lifetime.
        travel_mcp = await self._stack.enter_async_context(
            MCPStreamableHTTPTool(name="travel_tools", url=config.TRAVEL_MCP_URL)
        )
        cart_mcp = await self._stack.enter_async_context(
            MCPStreamableHTTPTool(name="cart_tools", url=config.CART_MCP_URL)
        )

        # Specialist sub-agents, exposed to the supervisor as callable tools.
        travel_agent = self._client.as_agent(
            name="travel_assistant",
            instructions=TRAVEL_AGENT_PROMPT,
            tools=[travel_mcp],
        )
        cart_agent = self._client.as_agent(
            name="cart_manager",
            instructions=CART_AGENT_PROMPT,
            tools=[cart_mcp],
        )

        self._travel_tool = travel_agent.as_tool(
            name="travel_assistant",
            description="Plan trips: flights, hotels, restaurants, attractions, weather and destination info.",
            arg_name="query",
            arg_description="The travel request, with dates (YYYY-MM-DD), airport codes and the user's id.",
        )
        self._cart_tool = cart_agent.as_tool(
            name="cart_manager",
            description="Manage the cart and checkout: view/add/remove items, change dates, onboard cards, purchase.",
            arg_name="query",
            arg_description="The cart/payment request, always including the user's id.",
        )

        self.cosmos = CosmosManager()
        itinerary_tools.set_cosmos(self.cosmos)
        logger.info("Concierge started.")

    async def stop(self) -> None:
        await self._stack.aclose()
        if self.cosmos:
            await self.cosmos.close()
        if self._client:
            await self._client.close()
        if self._credential:
            await self._credential.close()

    async def _user_profile_text(self, user_id: str) -> str:
        profile = await self.cosmos.get_user_profile(user_id) if self.cosmos else None
        parts = [f"User ID (use for all tool calls): {user_id}"]
        if profile:
            for key in ("name", "email", "address"):
                if profile.get(key):
                    parts.append(f"{key.title()}: {profile[key]}")
        return "; ".join(parts)

    def _supervisor(self, instructions: str) -> Agent:
        return Agent(
            self._client,
            instructions,
            name="travel_concierge",
            tools=[
                self._travel_tool,
                self._cart_tool,
                itinerary_tools.save_itinerary,
                itinerary_tools.clear_itinerary,
                search_visa_documentation,
            ],
        )

    def _session(self, user_id: str, session_id: str) -> AgentSession:
        key = f"{user_id}:{session_id}"
        if key not in self._sessions:
            self._sessions[key] = AgentSession(session_id=key)
        return self._sessions[key]

    async def stream(self, prompt: str, user_id: str, session_id: str):
        """Yield text chunks for the supervisor's streamed response."""
        profile = await self._user_profile_text(user_id)
        agent = self._supervisor(SUPERVISOR_PROMPT.format(user_profile=profile))
        session = self._session(user_id, session_id)
        async for update in agent.run(prompt, stream=True, session=session):
            if getattr(update, "text", None):
                yield update.text
