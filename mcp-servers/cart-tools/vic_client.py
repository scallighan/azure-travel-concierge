"""
Thin async MCP client used by the cart server to invoke sibling mock MCP
servers (server-to-server MCP call over streamable-http):

* ``call_vic_tool`` — the mock **VIC / VDP** service (tokenization + mandates +
  credentials), at ``VIC_MCP_URL``.
* ``call_merchant_tool`` — the mock **merchant / acquirer** service (settlement +
  order creation), at ``MERCHANT_MCP_URL``.
"""

import logging
import os

logger = logging.getLogger("cart-vic-client")

VIC_MCP_URL = os.getenv("VIC_MCP_URL", "")
MERCHANT_MCP_URL = os.getenv("MERCHANT_MCP_URL", "")


async def _call(url: str, tool_name: str, arguments: dict) -> dict:
    """Call a tool on an MCP streamable-http server and return its structured result."""
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    async with streamablehttp_client(url) as (read, write, _):
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


async def call_vic_tool(tool_name: str, arguments: dict) -> dict:
    """Call a tool on the mock VIC MCP server and return its structured result."""
    if not VIC_MCP_URL:
        raise RuntimeError("VIC_MCP_URL is not configured")
    return await _call(VIC_MCP_URL, tool_name, arguments)


async def call_merchant_tool(tool_name: str, arguments: dict) -> dict:
    """Call a tool on the mock merchant MCP server and return its structured result."""
    if not MERCHANT_MCP_URL:
        raise RuntimeError("MERCHANT_MCP_URL is not configured")
    return await _call(MERCHANT_MCP_URL, tool_name, arguments)


def merchant_configured() -> bool:
    """Whether a merchant settlement service is wired up."""
    return bool(MERCHANT_MCP_URL)
