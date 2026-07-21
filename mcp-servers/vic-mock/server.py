"""
Mock VIC MCP Server
=====================

A **demo-only** stand-in for the Visa Intelligent Commerce (VIC) / card
tokenization MCP server. It exposes the same conceptual capabilities as the
real VIC developer APIs (secure token, card enrollment + provisioning,
purchase initiation, payment credentials/cryptogram) so the rest of the
travel-concierge stack can be built and demonstrated end-to-end **without**
access to the real VIC sandbox.

Nothing here talks to a real payment network. Card data is never persisted;
only a synthetic, deterministic "provisioned token" is returned.

Transport: MCP streamable-http on ${PORT}/mcp
"""

import hashlib
import logging
import os
import random
import string
import time
from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vic-mock-mcp")

PORT = int(os.getenv("PORT", "8080"))

mcp = FastMCP("VIC Mock", host="0.0.0.0", port=PORT, stateless_http=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _rand(n: int, alphabet: str = string.ascii_uppercase + string.digits) -> str:
    return "".join(random.choices(alphabet, k=n))


def _luhn_last4(card_number: str) -> str:
    digits = "".join(c for c in card_number if c.isdigit())
    return digits[-4:] if len(digits) >= 4 else "0000"


def _card_brand(card_number: str) -> str:
    digits = "".join(c for c in card_number if c.isdigit())
    if digits.startswith("4"):
        return "Visa"
    if digits[:2] in {"51", "52", "53", "54", "55"}:
        return "Mastercard"
    if digits[:2] in {"34", "37"}:
        return "Amex"
    return "Visa"


def _deterministic_token(seed: str) -> str:
    h = hashlib.sha256(seed.encode()).hexdigest().upper()
    return f"VPTOK-{h[:24]}"


# ---------------------------------------------------------------------------
# MCP tools (mirror the real VIC server endpoints)
# ---------------------------------------------------------------------------
@mcp.tool()
def vic_secure_token() -> dict:
    """
    Issue a short-lived OAuth-style secure token used to authorize subsequent
    VIC API calls. (Mock: returns a random bearer token.)
    """
    return {
        "access_token": f"mock-vic-{_rand(40, string.ascii_letters + string.digits)}",
        "token_type": "Bearer",
        "expires_in": 3600,
        "issued_at": datetime.now(timezone.utc).isoformat(),
    }


@mcp.tool()
def vic_get_iframe_config(user_id: str) -> dict:
    """
    Return the configuration a front-end needs to render the secure card-entry
    iframe. In the mock, this points at the local mock card-capture form so no
    real VIC CSP-whitelisted domain is required.

    Args:
        user_id: The user onboarding a card.
    """
    return {
        "user_id": user_id,
        "iframe_url": "/vic-mock/card-capture",  # served by the web UI in mock mode
        "session_id": _rand(16),
        "public_key_id": "mock-pk-001",
        "mode": "mock",
        "message": "Mock VIC iframe. No real card data is transmitted.",
    }


@mcp.tool()
def vic_onboard_card(
    user_id: str,
    card_number: str,
    expiration_date: str,
    cvv: str = "",
    cardholder_name: str = "",
) -> dict:
    """
    Enroll a card and provision a network token (VIC tokenization).

    The PAN and CVV are used only to derive a synthetic token and are **never**
    stored or logged. Only the last four digits and brand are returned.

    Args:
        user_id: Owner of the card.
        card_number: Primary account number (PAN).
        expiration_date: Card expiry (MM/YY or MM/YYYY).
        cvv: Card verification value (ignored after token derivation).
        cardholder_name: Optional cardholder name.

    Returns:
        A provisioned token id plus non-sensitive card metadata.
    """
    last4 = _luhn_last4(card_number)
    brand = _card_brand(card_number)
    token = _deterministic_token(f"{user_id}:{card_number}:{expiration_date}")

    logger.info("Provisioned mock token for user=%s brand=%s last4=%s", user_id, brand, last4)

    return {
        "success": True,
        "vProvisionedTokenId": token,
        "card_brand": brand,
        "last4": last4,
        "expiration_date": expiration_date,
        "cardholder_name": cardholder_name,
        "token_status": "ACTIVE",
        "provisioned_at": datetime.now(timezone.utc).isoformat(),
    }


@mcp.tool()
def vic_initiate_purchase(
    user_id: str,
    provisioned_token_id: str,
    amount: float,
    currency: str = "USD",
    merchant_name: str = "Travel Concierge",
) -> dict:
    """
    Initiate a purchase against a previously provisioned token. Returns a
    purchase/transaction id that must be paired with payment credentials to
    settle. (Mock: always approves amounts below 100000.)

    Args:
        user_id: The paying user.
        provisioned_token_id: Token from vic_onboard_card.
        amount: Total amount to authorize.
        currency: ISO currency code.
        merchant_name: Merchant display name.
    """
    approved = 0 < amount < 100000
    return {
        "success": approved,
        "purchase_id": f"VPUR-{int(time.time())}-{_rand(6)}",
        "provisioned_token_id": provisioned_token_id,
        "amount": round(float(amount), 2),
        "currency": currency,
        "merchant_name": merchant_name,
        "status": "INITIATED" if approved else "DECLINED",
        "decline_reason": None if approved else "AMOUNT_LIMIT_EXCEEDED",
    }


@mcp.tool()
def vic_payment_credentials(
    purchase_id: str,
    provisioned_token_id: str,
) -> dict:
    """
    Return the payment credentials (network cryptogram + DPAN) used to settle a
    purchase. (Mock: synthetic cryptogram.)

    Args:
        purchase_id: Id from vic_initiate_purchase.
        provisioned_token_id: The token being charged.
    """
    return {
        "purchase_id": purchase_id,
        "dpan": f"411111{_rand(10, string.digits)}",
        "cryptogram": _rand(28, string.ascii_uppercase + string.digits),
        "eci": "05",
        "expiry": "12/29",
        "status": "AUTHORIZED",
        "authorized_at": datetime.now(timezone.utc).isoformat(),
    }


@mcp.tool()
def vic_health() -> dict:
    """Simple health/identity probe for the mock VIC server."""
    return {"service": "vic-mock-mcp", "status": "ok", "mode": "mock"}


if __name__ == "__main__":
    logger.info("Starting Mock VIC MCP server on :%s/mcp", PORT)
    mcp.run(transport="streamable-http")
