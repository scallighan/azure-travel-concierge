"""
Itinerary function tool exposed to the harness supervisor. Operates on the
process-wide Cosmos manager set at startup via ``set_cosmos``.
"""

from typing import Annotated

from pydantic import Field

from config import config
from cosmos_manager import CosmosManager
from mcp_direct import call_mcp_tool

_cosmos: CosmosManager | None = None


def set_cosmos(manager: CosmosManager) -> None:
    global _cosmos
    _cosmos = manager


async def save_itinerary(
    user_id: Annotated[str, Field(description="The user's unique id.")],
    itinerary_id: Annotated[str, Field(description="The id of the active itinerary to write to.")],
    items: Annotated[
        list[dict],
        Field(description="The complete desired itinerary items. Each: type, title, location, price, date, day, description, map_url (a Bing Maps link for hotels/restaurants/specific places; empty for flights)."),
    ],
) -> str:
    """Persist the full itinerary for the active itinerary_id so the UI can render it."""
    if _cosmos is None:
        return "Itinerary store unavailable."
    count = await _cosmos.save_items(user_id, itinerary_id, items)
    return f"Saved {count} item(s) to itinerary {itinerary_id}."


async def check_payment_card(
    user_id: Annotated[str, Field(description="The user's unique id.")],
) -> str:
    """Check whether the user has a payment card on file before starting checkout.

    Call this BEFORE delegating a purchase to the payments agent. If no card is on
    file, tell the user to add one via the "Add card" button in the payment panel
    and stop — do not attempt to book.
    """
    if not config.ENABLE_VIC:
        return "Payments are disabled; no card is required."
    if not config.CART_MCP_URL:
        return "Card status is unavailable right now."
    try:
        result = await call_mcp_tool(
            config.CART_MCP_URL, "cart_check_user_has_payment_card", {"user_id": user_id}
        )
    except Exception:  # noqa: BLE001 - surface a safe, actionable message
        return "Could not verify the payment card; ask the user to add a card via the payment panel before booking."
    if result.get("has_card"):
        brand = result.get("brand") or "card"
        last4 = result.get("last4") or "----"
        return f"Card on file: {brand} ending {last4}. OK to proceed to checkout."
    return (
        "NO CARD ON FILE. Do not book. Ask the user to add a payment card securely "
        'via the "Add card" button in the payment panel, then retry checkout once added.'
    )
