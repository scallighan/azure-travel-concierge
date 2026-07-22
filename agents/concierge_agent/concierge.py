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
from pathlib import Path

from azure.identity.aio import DefaultAzureCredential

from agent_framework import AgentSession, MCPStreamableHTTPTool, SkillsProvider, create_harness_agent
from agent_framework.foundry import FoundryChatClient
from agent_framework_azure_cosmos import CosmosHistoryProvider

import itinerary_tools
from config import config
from cosmos_manager import CosmosManager
from payments_agent import PaymentsAgent, payments_agent, set_payments
from prompts import PAYMENTS_AGENT_PROMPT, SUPERVISOR_PROMPT
from toolbox import build_toolbox_tool, resolve_version

logger = logging.getLogger("concierge")

# File-based Agent Harness skills live in ./skills (each subdirectory with a
# SKILL.md: flights, hotel-booking, food-entertainment, checkout). They are
# advertised to the supervisor and loaded on demand (progressive disclosure);
# the supervisor performs them itself using the shared toolbox / web-search
# tools passed to the harness.
SKILLS_DIR = Path(__file__).resolve().parent / "skills"


def _referenced_call_ids(messages) -> set[str]:
    """Collect every function-call id referenced by the given messages.

    Looks at ``call_id`` on function_call/function_result content and the nested
    ``function_call.call_id`` carried by approval request/response content. Used
    to protect a call the current run is actively resolving (a HITL approval /
    resume) from being sanitized away as if it were stale — on resume the harness
    supplies the matching result in-run, so the (still result-less) call in
    Cosmos history must be preserved.
    """
    ids: set[str] = set()
    for msg in messages or []:
        for content in getattr(msg, "contents", None) or []:
            cid = getattr(content, "call_id", None)
            if cid:
                ids.add(cid)
            nested = getattr(getattr(content, "function_call", None), "call_id", None)
            if nested:
                ids.add(nested)
    return ids


def _sanitize_history(messages: list, preserve_call_ids: frozenset[str] | set[str] = frozenset()) -> list:
    """Drop tool-call content that has no matching result.

    An interrupted run (e.g. a human-in-the-loop tool approval left unanswered,
    or a reboot mid-approval) can persist an assistant ``function_call`` to Cosmos
    without the corresponding ``function_result``. When that history is replayed,
    the Foundry Responses API rejects it with ``400 - No tool output found for
    function call ...`` and every subsequent turn fails. We repair the transcript
    on read by keeping only tool-related content whose ``call_id`` has both a call
    and a result, then dropping any messages left empty.

    ``preserve_call_ids`` are call ids the current run is actively resolving (an
    in-flight approval/resume). Their call is legitimately result-less in stored
    history because the result is produced during this very run — dropping it
    would orphan the result the harness is about to append and trigger the mirror
    error ``400 - No tool call found for function call output ...``. So we treat
    those ids as complete and keep them.
    """
    call_ids: set[str] = set()
    result_ids: set[str] = set()
    for msg in messages:
        for content in getattr(msg, "contents", None) or []:
            call_id = getattr(content, "call_id", None)
            if not call_id:
                continue
            if content.type == "function_call":
                call_ids.add(call_id)
            elif content.type == "function_result":
                result_ids.add(call_id)
    complete = (call_ids & result_ids) | set(preserve_call_ids)
    tool_types = {"function_call", "function_result", "function_approval_request", "function_approval_response"}

    cleaned: list = []
    for msg in messages:
        contents = getattr(msg, "contents", None)
        if not contents:
            cleaned.append(msg)
            continue
        kept = [
            c
            for c in contents
            if not (c.type in tool_types and getattr(c, "call_id", None) and c.call_id not in complete)
        ]
        if len(kept) == len(contents):
            cleaned.append(msg)
            continue
        if kept:
            msg.contents = kept
            cleaned.append(msg)
        # else: message had only dangling tool content -> drop it entirely
    return cleaned


class SanitizingCosmosHistoryProvider(CosmosHistoryProvider):
    """CosmosHistoryProvider that repairs dangling tool calls when loading history.

    See :func:`_sanitize_history`. Filtering on load (rather than mutating Cosmos)
    keeps existing corrupted itineraries usable and guards against future
    interruptions without a migration step. Sanitization happens in ``before_run``
    (not ``get_messages``) so it can consult the current run's input messages and
    preserve any call the run is actively resolving via a HITL approval/resume.
    """

    async def before_run(self, *, agent, session, context, state):
        history = await self.get_messages(context.session_id, state=state)
        preserve = _referenced_call_ids(context.input_messages)
        context.extend_messages(self, _sanitize_history(history, preserve))


class AGUISupervisor:
    """Adapts the per-request Concierge supervisor to the AG-UI protocol.

    ``add_agent_framework_fastapi_endpoint`` exposes a single ``SupportsAgentRun``.
    Because the concierge builds a fresh harness supervisor per turn (to inject the
    user profile + active itinerary into the instructions), this thin adapter
    resolves the active ``(user_id, itinerary_id)`` from each AG-UI run and
    delegates to the shared harness. The ids arrive via ``forwardedProps`` (and the
    AG-UI ``thread_id`` is ``"user_id:itinerary_id"``). Conversation memory stays in
    Cosmos, keyed by the ``AgentSession`` session_id (== the AG-UI thread_id).
    """

    def __init__(self, concierge: "Concierge") -> None:
        self._c = concierge
        self.id = "travel_concierge"
        self.name = "travel_concierge"
        self.description = "Azure Travel Concierge supervisor agent."

    def create_session(self, *, session_id: str | None = None) -> AgentSession:
        return AgentSession(session_id=session_id)

    def get_session(self, service_session_id, *, session_id: str | None = None) -> AgentSession:
        return AgentSession(service_session_id=service_session_id, session_id=session_id)

    @staticmethod
    def _resolve_ids(session: AgentSession | None) -> tuple[str, str]:
        user_id = itinerary_id = None
        meta = getattr(session, "metadata", None) or {}
        props = meta.get("forwarded_props") if isinstance(meta, dict) else None
        if isinstance(props, dict):
            user_id = props.get("user_id") or props.get("userId")
            itinerary_id = props.get("itinerary_id") or props.get("itineraryId")
        # Fallback: the AG-UI thread_id is the session id ("user_id:itinerary_id").
        sid = getattr(session, "session_id", None)
        if (not user_id or not itinerary_id) and sid:
            head, sep, tail = sid.rpartition(":")
            if sep and head and tail:
                user_id = user_id or head
                itinerary_id = itinerary_id or tail
        if not user_id or not itinerary_id:
            raise ValueError(
                "AG-UI run is missing user_id/itinerary_id "
                "(expected in forwardedProps or thread_id 'user_id:itinerary_id')."
            )
        return user_id, itinerary_id

    async def _build(self, session: AgentSession | None):
        user_id, itinerary_id = self._resolve_ids(session)
        profile = await self._c._user_profile_text(user_id)
        itin_ctx = await self._c._itinerary_context(user_id, itinerary_id)
        return self._c._supervisor(
            SUPERVISOR_PROMPT.format(user_profile=profile, itinerary_context=itin_ctx)
        )

    async def run(self, messages=None, *, stream: bool = False, session: AgentSession | None = None, **_kwargs):
        agent = await self._build(session)
        if stream:
            return agent.run(messages, stream=True, session=session)
        return await agent.run(messages, stream=False, session=session)


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
        self._skills: SkillsProvider | None = None
        self._tools: list = []
        self._disable_web_search = True

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

        # --- Foundry Toolbox (WebIQ + VIC) — shared by the file-based skills
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

        # The flights / hotel-booking / food-entertainment skills call these
        # shared tools. With the toolbox we force WebIQ (disable the built-in
        # web search); without it we let the harness provide web search.
        skill_tools = []
        if toolbox_tool is not None:
            skill_tools.append(toolbox_tool)
            self._disable_web_search = True
        else:
            self._disable_web_search = False

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
        self._history = SanitizingCosmosHistoryProvider(
            source_id="concierge",
            endpoint=config.COSMOS_ENDPOINT,
            database_name=config.COSMOS_DATABASE,
            container_name=config.COSMOS_HISTORY_CONTAINER,
            credential=self._history_credential,
        )

        self.cosmos = CosmosManager()
        itinerary_tools.set_cosmos(self.cosmos)

        # Discover the file-based skills once (SKILL.md under ./skills).
        self._skills = SkillsProvider.from_paths(str(SKILLS_DIR))

        self._tools = [
            *skill_tools,
            *([payment_tool] if payment_tool else []),
            itinerary_tools.save_itinerary,
            itinerary_tools.check_payment_card,
        ]
        logger.info("Concierge started (payments_foundry=%s, toolbox=%s, skills_dir=%s).",
                    self._payments.enabled, toolbox_tool is not None, SKILLS_DIR)

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
            skills_provider=self._skills,
            history_provider=self._history,
            disable_web_search=self._disable_web_search,
            disable_file_memory=True,
            # FoundryChatClient stores conversation state server-side by default
            # (STORES_BY_DEFAULT=True). Left as-is, the harness would treat the
            # CosmosHistoryProvider as a write-only sink and resume from a Foundry
            # server conversation instead -- but we pass a fresh AgentSession every
            # turn, so that conversation is always empty and the agent loses all
            # prior context. store=False makes the harness load and persist turn
            # history through the CosmosHistoryProvider (keyed by session_id).
            default_options={"store": False},
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

    def agui_agent(self) -> "AGUISupervisor":
        """Return the AG-UI protocol adapter over this concierge (SupportsAgentRun)."""
        return AGUISupervisor(self)
