"""
Cart Tools MCP Server
=====================

Cosmos-backed shopping cart, itinerary edits, payment-card onboarding and the
purchase flow. Payment tokenization/settlement is delegated to the **mock VIC
MCP server** (server-to-server MCP call), following the real Visa agentic
commerce flow: VTS PAN enrollment + token provisioning for onboarding, and
instruction + mandate -> credentials -> confirmation for checkout.

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
    Securely onboard a payment card. Mirrors the real Visa flow: enroll the PAN
    with VTS, provision a network token, then enroll that token for agentic
    commerce (VIC). The PAN is never stored — only the network token + last4.
    Args: user_id, card_number, expiration_date, cvv, cardholder_name.
    """
    if not ENABLE_VIC:
        return {"success": False, "error": "VIC integration disabled"}

    # Step 1 — VTS: enroll the PAN.
    enrollment = await call_vic_tool(
        "vic_enroll_pan",
        {
            "user_id": user_id,
            "card_number": card_number,
            "expiration_date": expiration_date,
            "cvv": cvv,
            "cardholder_name": cardholder_name,
        },
    )
    pan_enrollment_id = enrollment.get("vPanEnrollmentID")
    if not pan_enrollment_id:
        return {"success": False, "error": "PAN enrollment failed"}
    meta = enrollment.get("cardMetaData", {})

    # Step 2 — VTS: provision a network token for AI-agent presentation.
    provisioned = await call_vic_tool(
        "vic_provision_token", {"v_pan_enrollment_id": pan_enrollment_id}
    )
    token_id = provisioned.get("vProvisionedTokenID")
    if not token_id:
        return {"success": False, "error": f"Token provisioning failed: {provisioned.get('error')}"}

    # Step 3 — VIC: enroll the token for agentic commerce.
    enrolled = await call_vic_tool("vic_enroll_card", {"v_provisioned_token_id": token_id})
    if not enrolled.get("success"):
        return {"success": False, "error": f"Card enrollment failed: {enrolled.get('error')}"}

    card = {
        "vPanEnrollmentID": pan_enrollment_id,
        "vProvisionedTokenId": token_id,
        "last4": meta.get("last4"),
        "card_brand": meta.get("cardBrand"),
        "expiration_date": expiration_date,
        "status": enrolled.get("status", "ACTIVE"),
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
    Execute the purchase after the user confirms. Mirrors the real VIC agentic
    checkout: create an instruction carrying a spending mandate, retrieve
    per-transaction payment credentials, confirm the transaction outcome, then
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

    order_id = f"ORD-{datetime.now(timezone.utc):%Y%m%d}-{int(time.time()) % 100000}"
    payment_method = "Simulated"

    if ENABLE_VIC and card:
        token_id = card["vProvisionedTokenId"]
        prompt = f"Travel Concierge booking: {len(items)} item(s) totaling ${total}"

        # Step 1 — VIC: create an instruction with a spending mandate scoped to
        # the cart total (the user's delegated authorization to the agent).
        instruction = await call_vic_tool(
            "vic_create_instruction",
            {
                "user_id": user_id,
                "v_provisioned_token_id": token_id,
                "amount": total,
                "currency_code": "840",
                "prompt": prompt,
                "merchant_name": "Travel Concierge",
            },
        )
        if not instruction.get("success"):
            return {"success": False, "error": f"Could not authorize payment: {instruction.get('error')}"}
        instruction_id = instruction["instructionId"]

        # Step 2 — VIC: retrieve payment credentials for the transaction. The
        # mandate ceiling is enforced here.
        creds = await call_vic_tool(
            "vic_retrieve_credentials",
            {
                "instruction_id": instruction_id,
                "v_provisioned_token_id": token_id,
                "transactions": [
                    {
                        "merchant_name": "Travel Concierge",
                        "amount": total,
                        "currency_code": "840",
                    }
                ],
            },
        )
        approved = creds.get("credentials") or []
        if not approved:
            reason = (creds.get("declined") or [{}])[0].get("declineReason", creds.get("error", "declined"))
            return {"success": False, "error": f"Payment declined: {reason}"}
        transaction_reference_id = approved[0]["transactionReferenceId"]

        # Step 3 — VIC: confirm the transaction outcome back to VIC.
        confirmation = await call_vic_tool(
            "vic_confirm_transaction",
            {
                "instruction_id": instruction_id,
                "transaction_reference_id": transaction_reference_id,
                "amount": total,
                "currency_code": "840",
                "transaction_status": "APPROVED",
                "order_id": order_id,
            },
        )
        if not confirmation.get("success"):
            return {"success": False, "error": "Payment confirmation failed"}
        payment_method = f"{card['card_brand']} ending in {card['last4']}"

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
