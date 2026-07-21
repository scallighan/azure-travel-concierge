"""
Thin async MCP client used by the cart server to invoke the mock VIC MCP
server (server-to-server MCP call over streamable-http).
"""

import logging
import os

logger = logging.getLogger("cart-vic-client")

VIC_MCP_URL = os.getenv("VIC_MCP_URL", "")


async def call_vic_tool(tool_name: str, arguments: dict) -> dict:
    """Call a tool on the mock VIC MCP server and return its structured result."""
    if not VIC_MCP_URL:
        raise RuntimeError("VIC_MCP_URL is not configured")

    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    async with streamablehttp_client(VIC_MCP_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            # FastMCP returns structured content for dict-returning tools
            if getattr(result, "structuredContent", None):
                return result.structuredContent
            # Fallback: first text block
            for block in result.content or []:
                if getattr(block, "text", None):
                    import json

                    try:
                        return json.loads(block.text)
                    except Exception:
                        return {"raw": block.text}
            return {}
