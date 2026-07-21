"""
Cart Tools MCP Server
=====================

Cosmos-backed shopping cart, itinerary edits, payment-card onboarding and the
two-step purchase flow. Payment tokenization/settlement is delegated to the
**mock VIC MCP server** (server-to-server MCP call).

Transport: MCP streamable-http on ${PORT}/mcp
"""

import logging
import os
import re
import time
from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP

from cosmos_manager import CosmosManager
from vic_client import call_vic_tool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cart-tools-mcp")

PORT = int(os.getenv("PORT", "8080"))
ENABLE_VIC = os.getenv("ENABLE_VIC_INTEGRATION", "true").lower() == "true"

db = CosmosManager()
mcp = FastMCP("Cart Tools", host="0.0.0.0", port=PORT, stateless_http=True)


def _price_to_float(price) -> float:
    if isinstance(price, (int, float)):
        return float(price)
    m = re.search(r"[\d,]+(?:\.\d+)?", str(price or ""))
    return float(m.group().replace(",", "")) if m else 0.0


def _cart_total(items: list[dict]) -> float:
    return round(sum(_price_to_float(i.get("price")) for i in items), 2)


# --------------------------------------------------------------------- cart
@mcp.tool()
def cart_view_cart(user_id: str) -> dict:
    """View the contents of a user's cart. Args: user_id."""
    items = db.get_cart(user_id)
    return {"user_id": user_id, "items": items, "count": len(items), "total": _cart_total(items)}


@mcp.tool()
def cart_add_to_cart(user_id: str, items: list[dict]) -> dict:
    """
    Add one or more items to the cart. Each item needs a title and price; set
    item_type to "product", "hotel" or "flight" and include the type-specific
    id (asin/hotel_id/flight_id). Args: user_id, items.
    """
    added = [db.add_cart_item(user_id, it) for it in items]
    return {"success": True, "added": len(added), "items": added}


@mcp.tool()
def cart_remove_from_cart(user_id: str, identifiers: list[str], item_type: str = "product") -> dict:
    """Remove items by identifier (asin/hotel_id/flight_id). Args: user_id, identifiers, item_type."""
    removed = db.remove_cart_items(user_id, identifiers, item_type)
    return {"success": True, "removed": removed}


@mcp.tool()
def cart_clear_cart(user_id: str) -> dict:
    """Empty the entire cart. Args: user_id."""
    return {"success": True, "removed": db.clear_cart(user_id)}


@mcp.tool()
def cart_update_itinerary_date(user_id: str, identifier: str, item_type: str, new_date: str) -> dict:
    """
    Update a flight's departure date or a hotel's check-in date (YYYY-MM-DD).
    Args: user_id, identifier, item_type ("flight"|"hotel"), new_date.
    """
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", new_date):
        return {"success": False, "error": "new_date must be YYYY-MM-DD"}
    updated = db.update_item_date(user_id, identifier, item_type, new_date)
    return {"success": updated > 0, "updated": updated}


# ------------------------------------------------------------------ payment
@mcp.tool()
def cart_check_user_has_payment_card(user_id: str) -> dict:
    """Check whether the user already has a payment card on file. Args: user_id."""
    profile = db.get_user_profile(user_id) or {}
    card = profile.get("paymentCard")
    if card:
        return {"has_card": True, "last4": card.get("last4"), "brand": card.get("card_brand")}
    return {"has_card": False}


@mcp.tool()
async def cart_onboard_card(
    user_id: str,
    card_number: str,
    expiration_date: str,
    cvv: str = "",
    cardholder_name: str = "",
) -> dict:
    """
    Securely onboard a payment card. The PAN is tokenized by the VIC (mock)
    service; only the token + last4 are stored. Args: user_id, card_number,
    expiration_date, cvv, cardholder_name.
    """
    if not ENABLE_VIC:
        return {"success": False, "error": "VIC integration disabled"}
    token = await call_vic_tool(
        "vic_onboard_card",
        {
            "user_id": user_id,
            "card_number": card_number,
            "expiration_date": expiration_date,
            "cvv": cvv,
            "cardholder_name": cardholder_name,
        },
    )
    card = {
        "vProvisionedTokenId": token.get("vProvisionedTokenId"),
        "last4": token.get("last4"),
        "card_brand": token.get("card_brand"),
        "expiration_date": token.get("expiration_date"),
    }
    db.set_payment_card(user_id, card)
    return {"success": True, "card": card}


@mcp.tool()
async def cart_get_vic_iframe_config(user_id: str) -> dict:
    """Get the config the UI needs to render the secure card-entry iframe. Args: user_id."""
    if not ENABLE_VIC:
        return {"enabled": False}
    cfg = await call_vic_tool("vic_get_iframe_config", {"user_id": user_id})
    return {"enabled": True, **cfg}


@mcp.tool()
def cart_request_purchase_confirmation(user_id: str) -> dict:
    """
    Prepare a purchase summary (total + payment method) that MUST be shown to
    the user before cart_confirm_purchase. Args: user_id.
    """
    items = db.get_cart(user_id)
    if not items:
        return {"requires_confirmation": False, "error": "Cart is empty"}
    total = _cart_total(items)
    profile = db.get_user_profile(user_id) or {}
    card = profile.get("paymentCard")
    return {
        "requires_confirmation": True,
        "total_amount": total,
        "total_items": len(items),
        "payment_method": f"{card.get('card_brand')} ending in {card.get('last4')}" if card else None,
        "has_card": bool(card),
        "message": f"Ready to purchase {len(items)} item(s) for ${total}. Confirm to proceed.",
    }


@mcp.tool()
async def cart_confirm_purchase(user_id: str) -> dict:
    """
    Execute the purchase after the user confirms: authorize via VIC (mock),
    create an order and clear the cart. Args: user_id.
    """
    items = db.get_cart(user_id)
    if not items:
        return {"success": False, "error": "Cart is empty"}
    total = _cart_total(items)
    profile = db.get_user_profile(user_id) or {}
    card = profile.get("paymentCard")
    if ENABLE_VIC and not card:
        return {"success": False, "error": "No payment card on file"}

    payment_method = "Simulated"
    if ENABLE_VIC and card:
        purchase = await call_vic_tool(
            "vic_initiate_purchase",
            {
                "user_id": user_id,
                "provisioned_token_id": card["vProvisionedTokenId"],
                "amount": total,
                "currency": "USD",
            },
        )
        if not purchase.get("success"):
            return {"success": False, "error": f"Payment declined: {purchase.get('decline_reason')}"}
        await call_vic_tool(
            "vic_payment_credentials",
            {"purchase_id": purchase["purchase_id"], "provisioned_token_id": card["vProvisionedTokenId"]},
        )
        payment_method = f"{card['card_brand']} ending in {card['last4']}"

    order_id = f"ORD-{datetime.now(timezone.utc):%Y%m%d}-{int(time.time()) % 100000}"
    order = {
        "order_id": order_id,
        "total_amount": total,
        "items_count": len(items),
        "items": items,
        "payment_method": payment_method,
        "status": "CONFIRMED",
    }
    db.create_order(user_id, order)
    db.clear_cart(user_id)

    # NOTE: purchase-confirmation notifications (email) will be handled by WorkIQ.
    return {"success": True, "order_id": order_id, "total_amount": total,
            "items_count": len(items), "payment_method": payment_method}


if __name__ == "__main__":
    logger.info("Starting Cart Tools MCP server on :%s/mcp (vic=%s)", PORT, ENABLE_VIC)
    mcp.run(transport="streamable-http")
