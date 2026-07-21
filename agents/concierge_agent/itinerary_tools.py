"""
Itinerary function tool exposed to the harness supervisor. Operates on the
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
    itinerary_id: Annotated[str, Field(description="The id of the active itinerary to write to.")],
    items: Annotated[
        list[dict],
        Field(description="The complete desired itinerary items. Each: type, title, location, price, date, day, description."),
    ],
) -> str:
    """Persist the full itinerary for the active itinerary_id so the UI can render it."""
    if _cosmos is None:
        return "Itinerary store unavailable."
    count = await _cosmos.save_items(user_id, itinerary_id, items)
    return f"Saved {count} item(s) to itinerary {itinerary_id}."
