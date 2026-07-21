"""
Itinerary function tools exposed to the supervisor agent. They operate on the
process-wide Cosmos manager set at startup via ``set_cosmos``.
"""

from typing import Annotated

from pydantic import Field

from cosmos_manager import CosmosManager

_cosmos: CosmosManager | None = None


def set_cosmos(manager: CosmosManager) -> None:
    global _cosmos
    _cosmos = manager


async def save_itinerary(
    user_id: Annotated[str, Field(description="The user's unique id.")],
    items: Annotated[
        list[dict],
        Field(description="Itinerary items. Each: type, title, location, price, date, day, description."),
    ],
) -> str:
    """Persist a complete itinerary for the user so the UI can render it."""
    if _cosmos is None:
        return "Itinerary store unavailable."
    count = await _cosmos.save_itinerary(user_id, items)
    return f"Saved {count} itinerary item(s)."


async def clear_itinerary(
    user_id: Annotated[str, Field(description="The user's unique id.")],
) -> str:
    """Remove all saved itinerary items for the user."""
    if _cosmos is None:
        return "Itinerary store unavailable."
    count = await _cosmos.clear_itinerary(user_id)
    return f"Cleared {count} itinerary item(s)."
