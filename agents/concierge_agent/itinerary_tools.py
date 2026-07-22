"""
Itinerary function tool exposed to the harness supervisor. Operates on the
process-wide Cosmos manager set at startup via ``set_cosmos``.
"""

from typing import Annotated

from pydantic import Field

from config import config
from cosmos_manager import CosmosManager
from mcp_direct import call_mcp_tool

import logging
import re
import uuid
from datetime import datetime, timezone

logger = logging.getLogger("itinerary-tools")

_cosmos: CosmosManager | None = None


def set_cosmos(manager: CosmosManager) -> None:
    global _cosmos
    _cosmos = manager


async def save_itinerary(
    user_id: Annotated[str, Field(description="The user's unique id.")],
    itinerary_id: Annotated[str, Field(description="The id of the active itinerary to write to.")],
    items: Annotated[
        list[dict],
        Field(description="The complete desired itinerary items. Each: type, title, location, price, date, day, description, map_url (a Bing Maps link for hotels/restaurants/specific places; empty for flights), booking_url (a real booking link — required for flights, empty for other types)."),
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


# ---------------------------------------------------------------------------
# Order recording (called by the payments tool after a successful checkout)
# ---------------------------------------------------------------------------
_ORDER_ID_RE = re.compile(r"\bORD-[A-Z0-9][A-Z0-9-]*", re.IGNORECASE)
_TXN_RE = re.compile(r"\bVTXN-[A-Z0-9][A-Z0-9-]*", re.IGNORECASE)
_SUCCESS_RE = re.compile(r"\b(success|succeeded|completed|complete|approved|confirmed|booked)\b", re.IGNORECASE)
_FAILURE_RE = re.compile(
    r"\b(fail(?:ed|ure)?|declin(?:e|ed)|error|unavailable|couldn'?t|could not|unable|not\s+available)\b",
    re.IGNORECASE,
)
_AMOUNT_RE = re.compile(r"(?:USD|US\$|\$)\s*([\d,]+(?:\.\d{1,2})?)", re.IGNORECASE)
_NUM_RE = re.compile(r"[\d,]+(?:\.\d{1,2})?")


def _price_to_float(price) -> float:
    """Best-effort parse of a price string/number to a float (0.0 on failure)."""
    if price is None:
        return 0.0
    if isinstance(price, (int, float)):
        return float(price)
    m = _NUM_RE.search(str(price))
    if not m:
        return 0.0
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return 0.0


def _looks_successful(text: str) -> bool:
    """Heuristic: a Foundry checkout succeeded if it reports a VIC transaction /
    order reference or a success keyword, and does not read as a failure."""
    if not text:
        return False
    if _TXN_RE.search(text) or _ORDER_ID_RE.search(text):
        return True
    return bool(_SUCCESS_RE.search(text) and not _FAILURE_RE.search(text))


async def record_order(user_id: str, itinerary_id: str, confirmation_text: str) -> str | None:
    """Snapshot the confirmed itinerary into an order after a successful checkout.

    Called by the payments tool once the Foundry payments agent reports success.
    Returns the recorded ``order_id`` (idempotent by order_id), or ``None`` when
    nothing was recorded (unavailable store, no items, or unrecognized outcome).
    Best-effort: never raises into the caller.
    """
    if _cosmos is None:
        return None
    if not _looks_successful(confirmation_text):
        logger.info("record_order: outcome not recognized as success; skipping (user=%s).", user_id)
        return None
    try:
        items = await _cosmos.get_items(user_id, itinerary_id)
        txn_match = _TXN_RE.search(confirmation_text or "")
        ord_match = _ORDER_ID_RE.search(confirmation_text or "")
        transaction_reference = txn_match.group(0) if txn_match else None
        order_id = (
            (ord_match.group(0) if ord_match else None)
            or transaction_reference
            or f"ORD-{datetime.now(timezone.utc):%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"
        )

        # Prefer the total stated by the merchant/VIC; fall back to summing items.
        amt_match = _AMOUNT_RE.search(confirmation_text or "")
        total = (
            float(amt_match.group(1).replace(",", ""))
            if amt_match
            else round(sum(_price_to_float(it.get("price")) for it in items), 2)
        )

        # Best-effort payment method (brand + last4) for a nicer receipt.
        payment_method = None
        if config.ENABLE_VIC and config.CART_MCP_URL:
            try:
                card = await call_mcp_tool(
                    config.CART_MCP_URL, "cart_check_user_has_payment_card", {"user_id": user_id}
                )
                if card.get("has_card"):
                    payment_method = f"{card.get('brand') or 'card'} ending {card.get('last4') or '----'}"
            except Exception:  # noqa: BLE001 - receipt detail only
                payment_method = None

        order = {
            "order_id": order_id,
            "itinerary_id": itinerary_id,
            "status": "CONFIRMED",
            "total_amount": total,
            "currency": "USD",
            "items_count": len(items),
            "items": items,
            "payment_method": payment_method,
            "transaction_reference": transaction_reference,
            "confirmation_summary": (confirmation_text or "")[:500],
        }
        await _cosmos.create_order(user_id, order)
        logger.info("record_order: saved order %s (user=%s, %d item(s), total=%.2f).",
                    order_id, user_id, len(items), total)
        return order_id
    except Exception:  # noqa: BLE001 - order recording must never break checkout
        logger.exception("record_order: failed to persist order (user=%s).", user_id)
        return None
