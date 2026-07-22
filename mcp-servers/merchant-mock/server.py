"""
Mock **merchant / acquirer** MCP server for the Travel Concierge.

In the real Visa Intelligent Commerce (VIC) agentic-commerce flow the *merchant*
is a separate party from Visa (VDP). The agent obtains a spending **mandate** and
retrieves per-transaction network-token **credentials** from Visa (our
``vic-mock`` service), then **presents those credentials to the merchant**, who
authorizes/settles the charge with the network and creates the order. The
merchant only ever sees a network token (DPAN) + cryptogram — never the real PAN.

This service plays that merchant role. It exposes ``merchant_authorize`` (accept
network-token credentials, approve/decline, create an order), ``merchant_get_order``
and ``merchant_health``. It keeps no product catalog — the travel domain lives in
``travel-tools`` — only the settlement/order boundary.

Mirrors the reference project's ``reference-merchant-backend`` / ``reference-merchant-mcp``
(https://github.com/visa/vic-reference-agent) settlement responsibility.

Transport: MCP streamable-http on ${PORT}/mcp
"""

import logging
import os
import random
import string
import threading
import time
from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("merchant-mock-mcp")

PORT = int(os.getenv("PORT", "8080"))
MERCHANT_NAME = os.getenv("MERCHANT_NAME", "Travel Concierge")

# Coarse "acquirer" ceiling for demos. Unset by default (``None``) so the mock
# approves any positive amount — set ``MERCHANT_DECLINE_CEILING`` to a number to
# re-enable amount-based declines for testing.
_ceiling_env = os.getenv("MERCHANT_DECLINE_CEILING", "").strip()
DECLINE_CEILING: float | None = float(_ceiling_env) if _ceiling_env else None

mcp = FastMCP("Merchant Mock", host="0.0.0.0", port=PORT, stateless_http=True)


# ---------------------------------------------------------------------------
# In-memory order store. Single-process demo store only — run one replica.
# ---------------------------------------------------------------------------
_lock = threading.Lock()
_orders: dict[str, dict] = {}          # keyed by merchant order id
_seen_txn: dict[str, str] = {}         # transactionReferenceId -> order id (idempotency)


def _rand(n: int, alphabet: str = string.ascii_uppercase + string.digits) -> str:
    return "".join(random.choices(alphabet, k=n))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@mcp.tool()
def merchant_authorize(
    amount: float,
    payment_credentials: dict,
    currency_code: str = "840",
    order_reference: str = "",
    merchant_name: str = "",
    items: list[dict] | None = None,
) -> dict:
    """
    Authorize and settle a purchase using VIC network-token **credentials** and
    create the merchant order. This is the merchant side of agentic checkout:
    the agent has already retrieved per-transaction credentials from Visa
    (``vic_retrieve_credentials``) and now presents them here to complete the
    sale. The merchant validates the credentials (network token + cryptogram),
    approves or declines, records the order, and returns an authorization code.

    The card PAN is never involved — only the DPAN (``paymentToken``) and
    cryptogram from the VIC credentials.

    Args:
        amount: The transaction amount to settle.
        payment_credentials: One credential object from
            ``vic_retrieve_credentials`` (``transactionReferenceId``,
            ``paymentToken`` (DPAN), ``cryptogram``, ``dynamicDataValue`` (dCVV2),
            ``tokenExpirationMonth``/``Year``, ``eci``).
        currency_code: ISO 4217 numeric currency (e.g. "840" = USD).
        order_reference: Optional caller-side reference (e.g. the cart order id).
        merchant_name: Merchant display name (defaults to the service default).
        items: Optional line items for the order record.
    """
    creds = payment_credentials or {}
    txn_ref = creds.get("transactionReferenceId")
    dpan = creds.get("paymentToken")
    cryptogram = creds.get("cryptogram")
    amount = round(float(amount or 0), 2)
    merchant = merchant_name or MERCHANT_NAME

    # Validate the network-token credentials the agent presented.
    if not txn_ref or not dpan or not cryptogram:
        return {
            "approved": False,
            "declineReason": "INVALID_CREDENTIALS",
            "error": "Missing network-token credentials (transactionReferenceId, paymentToken, cryptogram).",
        }
    if amount <= 0:
        return {"approved": False, "transactionReferenceId": txn_ref, "declineReason": "INVALID_AMOUNT"}
    if DECLINE_CEILING is not None and amount >= DECLINE_CEILING:
        return {"approved": False, "transactionReferenceId": txn_ref, "declineReason": "AMOUNT_LIMIT_EXCEEDED"}

    with _lock:
        # Idempotency: the same VIC transaction settles to the same order.
        existing = _seen_txn.get(txn_ref)
        if existing:
            order = _orders[existing]
            return {
                "approved": True,
                "orderId": order["order_id"],
                "authorizationCode": order["authorization_code"],
                "transactionReferenceId": txn_ref,
                "amount": order["amount"],
                "currencyCode": order["currency_code"],
                "status": order["status"],
                "duplicate": True,
                "settled_at": order["settled_at"],
            }

        order_id = f"MRCH-{datetime.now(timezone.utc):%Y%m%d}-{int(time.time()) % 100000}"
        auth_code = _rand(6)
        order = {
            "order_id": order_id,
            "order_reference": order_reference or None,
            "merchant_name": merchant,
            "amount": amount,
            "currency_code": currency_code,
            "authorization_code": auth_code,
            "transaction_reference_id": txn_ref,
            "network_token_last4": str(dpan)[-4:],
            "eci": creds.get("eci"),
            "items": items or [],
            "status": "AUTHORIZED",
            "settled_at": _now_iso(),
        }
        _orders[order_id] = order
        _seen_txn[txn_ref] = order_id

    logger.info("Merchant authorized %s %s -> order=%s auth=%s", amount, currency_code, order_id, auth_code)
    return {
        "approved": True,
        "orderId": order_id,
        "authorizationCode": auth_code,
        "transactionReferenceId": txn_ref,
        "amount": amount,
        "currencyCode": currency_code,
        "status": "AUTHORIZED",
        "settled_at": order["settled_at"],
    }


@mcp.tool()
def merchant_get_order(order_id: str) -> dict:
    """
    Look up a merchant order previously created by ``merchant_authorize``.

    Args:
        order_id: The merchant order id (e.g. ``MRCH-20260101-12345``).
    """
    with _lock:
        order = _orders.get(order_id)
    if order is None:
        return {"found": False}
    return {"found": True, **order}


@mcp.tool()
def merchant_health() -> dict:
    """Liveness/readiness probe. Returns ``{"status": "ok", "mode": "mock"}``."""
    with _lock:
        count = len(_orders)
    return {"status": "ok", "mode": "mock", "merchant": MERCHANT_NAME, "orders": count}


if __name__ == "__main__":
    logger.info("Starting Merchant Mock MCP server on :%s/mcp", PORT)
    mcp.run(transport="streamable-http")
