"""
Direct MCP tool invocation from the agent process (bypassing the LLM).

Used by the REST endpoints that back the UI's cart/itinerary panels and the
secure card-onboarding flow — card data must never pass through the model.
"""

import json
import logging

logger = logging.getLogger("mcp-direct")


async def call_mcp_tool(url: str, tool_name: str, arguments: dict) -> dict:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    async with streamablehttp_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            if getattr(result, "structuredContent", None):
                return result.structuredContent
            for block in result.content or []:
                text = getattr(block, "text", None)
                if text:
                    try:
                        return json.loads(text)
                    except Exception:
                        return {"raw": text}
            return {}
