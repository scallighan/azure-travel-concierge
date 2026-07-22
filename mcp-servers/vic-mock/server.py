"""
Mock VIC MCP Server
=====================

A **demo-only** stand-in for Visa Intelligent Commerce (VIC). It mirrors the
shape and flow of the real Visa reference agent backend
(https://github.com/visa/vic-reference-agent) so the rest of the
travel-concierge stack can be built and demonstrated end-to-end **without**
access to the real Visa Developer Platform (VDP) sandbox.

The real backend orchestrates two Visa services:

* **VTS** (Visa Token Service) — card enrollment + network-token provisioning:
  ``panEnrollments`` -> ``provisionedTokens`` (yields a ``vProvisionedTokenID``).
* **VIC / VACP** (Visa Agentic Commerce Platform) — the ``/vacp/*`` endpoints:
  enroll the token for agentic commerce (``cards``), create an **instruction**
  carrying a spending **mandate** (``instructions``), retrieve per-transaction
  payment **credentials** (``instructions/{id}/credentials``), then **confirm**
  the transaction outcome (``instructions/{id}/confirmations``).

This mock keeps the same field names (``vPanEnrollmentID``,
``vProvisionedTokenID``, ``instructionId``, ``mandateId``,
``transactionReferenceId``, ``dynamicDataId``, ``declineThreshold`` ...), the
same state transitions, the same enums, and the same call ordering — but it
performs **no** real cryptography (no JWE/MLE, no HMAC ``x-pay-token``) and
never talks to a payment network. Card data is never persisted; only a
synthetic, deterministic network token is derived.

Transport: MCP streamable-http on ${PORT}/mcp
"""

import hashlib
import logging
import os
import random
import string
import threading
import time
from datetime import datetime, timedelta, timezone

from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vic-mock-mcp")

PORT = int(os.getenv("PORT", "8080"))

# Default number of days a mandate (spending authorization) stays effective,
# mirroring the reference backend's `epoch + 3 days`.
MANDATE_EFFECTIVE_DAYS = int(os.getenv("VIC_MANDATE_EFFECTIVE_DAYS", "3"))

mcp = FastMCP("VIC Mock", host="0.0.0.0", port=PORT, stateless_http=True)


# ---------------------------------------------------------------------------
# Enums (mirror src/enums.py + constants.py in the reference backend)
# ---------------------------------------------------------------------------
INTENT_ACTIVE = "ACTIVE"
INTENT_IN_PROGRESS = "IN PROGRESS"  # note the space, as in the real enum
INTENT_CANCELLED = "CANCELLED"

MANDATE_ACTIVE = "ACTIVE"
MANDATE_DELETED = "DELETED"

TXN_ACTIVE = "ACTIVE"
TXN_SUCCESS = "SUCCESS"
TXN_FAILURE = "FAILURE"

CARD_PENDING = "PENDING"
CARD_ACTIVE = "ACTIVE"

TOKEN_ACTIVE = "ACTIVE"
TOKEN_DELETED = "DELETED"

TXN_STATUS_APPROVED = "APPROVED"
TXN_STATUS_DECLINED = "DECLINED"

PRESENTATION_TYPE_AI_AGENT = "AI_AGENT"
PROTECTION_TYPE_CLOUD = "CLOUD"
ACCOUNT_TYPE_WALLET = "WALLET"
PAN_SOURCE_MANUAL = "MANUALLYENTERED"
CONSUMER_ENTRY_MODE_KEY = "KEYENTERED"
ENROLLMENT_REFERENCE_TYPE_TOKEN = "TOKEN_REFERENCE_ID"
ENROLLMENT_REFERENCE_PROVIDER_VTS = "VTS"
TRANSACTION_TYPE_PURCHASE = "PURCHASE"

# Purchases at/above this amount are declined by the mock authorizer even when a
# mandate would otherwise allow them (a coarse "issuer" ceiling for demos).
HARD_DECLINE_CEILING = 100000.0


# ---------------------------------------------------------------------------
# In-memory state. A real deployment persists this in a database; the mock keeps
# just enough server-side state to enforce the flow (token must be provisioned
# before a card can be enrolled, an active mandate is required before credentials
# can be retrieved, mandates carry a spend ceiling, etc.).
#
# NOTE: single-process demo store only. Run the mock with a single replica.
# ---------------------------------------------------------------------------
_lock = threading.Lock()
_pan_enrollments: dict[str, dict] = {}
_tokens: dict[str, dict] = {}
_vic_cards: dict[str, dict] = {}      # keyed by vProvisionedTokenID
_user_cards: dict[str, str] = {}      # user_id -> active vProvisionedTokenID (relationship index)
_instructions: dict[str, dict] = {}
_mandates: dict[str, dict] = {}
_transactions: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _rand(n: int, alphabet: str = string.ascii_uppercase + string.digits) -> str:
    return "".join(random.choices(alphabet, k=n))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _digits(card_number: str) -> str:
    return "".join(c for c in str(card_number) if c.isdigit())


def _last4(card_number: str) -> str:
    d = _digits(card_number)
    return d[-4:] if len(d) >= 4 else "0000"


def _card_brand(card_number: str) -> str:
    d = _digits(card_number)
    if d.startswith("4"):
        return "Visa"
    if d[:2] in {"51", "52", "53", "54", "55"}:
        return "Mastercard"
    if d[:2] in {"34", "37"}:
        return "Amex"
    return "Visa"


def _parse_expiry(expiration_date: str) -> tuple[int, int]:
    """Parse 'MM/YY' or 'MM/YYYY' into (month, year). Best-effort for the mock."""
    parts = str(expiration_date or "").replace("-", "/").split("/")
    try:
        month = int(parts[0])
    except (ValueError, IndexError):
        month = 12
    year = 0
    if len(parts) > 1:
        try:
            year = int(parts[1])
        except ValueError:
            year = 0
    if year and year < 100:
        year += 2000
    if not year:
        year = datetime.now(timezone.utc).year + 3
    return month, year


def _deterministic_token(seed: str) -> str:
    h = hashlib.sha256(seed.encode()).hexdigest().upper()
    return f"VPTOK-{h[:24]}"


def _dpan(seed: str) -> str:
    """Deterministic 16-digit network token PAN (DPAN) starting with a Visa BIN."""
    h = int(hashlib.sha256(seed.encode()).hexdigest(), 16)
    return "411111" + str(h % 10**10).zfill(10)


# ---------------------------------------------------------------------------
# Session / auth helpers (real backend signs an x-pay-token per request)
# ---------------------------------------------------------------------------
@mcp.tool()
def vic_secure_token() -> dict:
    """
    Issue a short-lived secure token used to authorize subsequent VIC API calls.
    (Mock stand-in for the HMAC ``x-pay-token`` the real client signs per call.)
    """
    return {
        "access_token": f"mock-vic-{_rand(40, string.ascii_letters + string.digits)}",
        "token_type": "Bearer",
        "expires_in": 3600,
        "issued_at": _now_iso(),
    }


@mcp.tool()
def vic_get_public_key() -> dict:
    """
    Return the (mock) public key a front-end would use to JWE-encrypt card data
    before sending it for PAN enrollment. In the real backend this is an
    ephemeral RSA-2048 public key; here it is a stable placeholder so no real
    card data is ever encrypted or transmitted.
    """
    return {
        "keyId": "mock-mle-key-001",
        "algorithm": "RSA-OAEP-256",
        "publicKey": "-----BEGIN PUBLIC KEY-----\nMOCK-VIC-DEMO-KEY\n-----END PUBLIC KEY-----",
        "mode": "mock",
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
        "public_key_id": "mock-mle-key-001",
        "mode": "mock",
        "message": "Mock VIC iframe. No real card data is transmitted.",
    }


# ---------------------------------------------------------------------------
# VTS — card enrollment & network-token provisioning
# ---------------------------------------------------------------------------
@mcp.tool()
def vic_enroll_pan(
    user_id: str,
    card_number: str,
    expiration_date: str,
    cvv: str = "",
    cardholder_name: str = "",
) -> dict:
    """
    Enroll a PAN with the Visa Token Service (VTS ``panEnrollments``).

    The PAN and CVV are used only to derive synthetic identifiers and are
    **never** stored or logged. Returns a ``vPanEnrollmentID`` plus non-sensitive
    ``cardMetaData``. This is step 1 of card onboarding; follow with
    ``vic_provision_token``.

    Args:
        user_id: Owner of the card.
        card_number: Primary account number (PAN).
        expiration_date: Card expiry (MM/YY or MM/YYYY).
        cvv: Card verification value (ignored after derivation).
        cardholder_name: Optional cardholder name.
    """
    last4 = _last4(card_number)
    brand = _card_brand(card_number)
    month, year = _parse_expiry(expiration_date)
    pan_enrollment_id = "VPAN-" + hashlib.sha256(
        f"{user_id}:{_digits(card_number)}".encode()
    ).hexdigest()[:20].upper()

    with _lock:
        _pan_enrollments[pan_enrollment_id] = {
            "user_id": user_id,
            "last4": last4,
            "brand": brand,
            "exp_month": month,
            "exp_year": year,
            "status": CARD_PENDING,
        }

    logger.info("VTS panEnrollment for user=%s brand=%s last4=%s", user_id, brand, last4)
    return {
        "vPanEnrollmentID": pan_enrollment_id,
        "panSource": PAN_SOURCE_MANUAL,
        "consumerEntryMode": CONSUMER_ENTRY_MODE_KEY,
        "cardMetaData": {
            "cardBrand": brand,
            "last4": last4,
            "cardholderName": cardholder_name,
            "expirationDate": {"month": month, "year": year},
            "cardData": [
                {"contentType": "digitalCardArt", "guid": f"art-{pan_enrollment_id[-8:]}"}
            ],
        },
        "enrolled_at": _now_iso(),
    }


@mcp.tool()
def vic_provision_token(v_pan_enrollment_id: str) -> dict:
    """
    Provision a network token for an enrolled PAN (VTS
    ``panEnrollments/{id}/provisionedTokens``). Returns a ``vProvisionedTokenID``
    and ``tokenInfo``. This is step 2 of card onboarding; the token is
    provisioned for ``AI_AGENT`` presentation with ``CLOUD`` protection.

    Args:
        v_pan_enrollment_id: The ``vPanEnrollmentID`` from ``vic_enroll_pan``.
    """
    with _lock:
        enrollment = _pan_enrollments.get(v_pan_enrollment_id)
        if enrollment is None:
            return {"success": False, "error": "Unknown vPanEnrollmentID; call vic_enroll_pan first."}

        token_id = _deterministic_token(v_pan_enrollment_id)
        _tokens[token_id] = {
            "user_id": enrollment["user_id"],
            "pan_enrollment_id": v_pan_enrollment_id,
            "last4": enrollment["last4"],
            "brand": enrollment["brand"],
            "exp_month": enrollment["exp_month"],
            "exp_year": enrollment["exp_year"],
            "status": TOKEN_ACTIVE,
        }

    return {
        "vProvisionedTokenID": token_id,
        "tokenInfo": {
            "tokenLast4": enrollment["last4"],
            "tokenStatus": TOKEN_ACTIVE,
            "tokenExpirationMonth": enrollment["exp_month"],
            "tokenExpirationYear": enrollment["exp_year"],
            "presentationType": [PRESENTATION_TYPE_AI_AGENT],
            "protectionType": PROTECTION_TYPE_CLOUD,
            "accountType": ACCOUNT_TYPE_WALLET,
        },
        "provisioned_at": _now_iso(),
    }


@mcp.tool()
def vic_enroll_card(v_provisioned_token_id: str) -> dict:
    """
    Enroll a provisioned token for agentic commerce (VIC ``/vacp/v1/cards``).
    Binds the network token to the AI-agent presentation so it can be used with
    instructions/mandates. This is step 3 of onboarding; on success the card is
    ``ACTIVE`` and ready for agentic checkout.

    Args:
        v_provisioned_token_id: The ``vProvisionedTokenID`` from ``vic_provision_token``.
    """
    with _lock:
        token = _tokens.get(v_provisioned_token_id)
        if token is None:
            return {"success": False, "error": "Unknown vProvisionedTokenID; call vic_provision_token first."}
        if token["status"] != TOKEN_ACTIVE:
            return {"success": False, "error": f"Token is {token['status']}, cannot enroll."}

        card_id = "VCARD-" + hashlib.sha256(v_provisioned_token_id.encode()).hexdigest()[:16].upper()
        _vic_cards[v_provisioned_token_id] = {
            "card_id": card_id,
            "user_id": token["user_id"],
            "status": CARD_ACTIVE,
        }
        # Index the card by user so it can be looked up with only a user_id
        # (this is the relationship the app stores a pointer to in Cosmos).
        _user_cards[token["user_id"]] = v_provisioned_token_id

    return {
        "success": True,
        "cardId": card_id,
        "status": CARD_ACTIVE,
        "enrollmentReferenceType": ENROLLMENT_REFERENCE_TYPE_TOKEN,
        "enrollmentReferenceProvider": ENROLLMENT_REFERENCE_PROVIDER_VTS,
        "enrolled_at": _now_iso(),
    }


@mcp.tool()
def vic_get_card(user_id: str) -> dict:
    """
    Look up the payment card a user currently has on file with VIC — the source
    of truth for card state. VIC is keyed by ``vProvisionedTokenID``; this tool
    resolves that token from a ``user_id`` relationship index built during
    ``vic_enroll_card``, so callers holding only a ``user_id`` (e.g. the payments
    agent, or the cart's card-status check) can verify a card and obtain the
    token needed to transact — without the card details ever being stored
    outside VIC.

    Returns ``{"has_card": True, "vProvisionedTokenId", "last4", "card_brand",
    "status", ...}`` when an ACTIVE card exists, otherwise ``{"has_card": False}``.

    Args:
        user_id: The user whose card to look up.
    """
    with _lock:
        token_id = _user_cards.get(user_id)
        if not token_id:
            return {"has_card": False}
        card = _vic_cards.get(token_id)
        token = _tokens.get(token_id)
        if card is None or token is None or card.get("status") != CARD_ACTIVE:
            return {"has_card": False}
        return {
            "has_card": True,
            "vProvisionedTokenId": token_id,
            "cardId": card["card_id"],
            "last4": token["last4"],
            "card_brand": token["brand"],
            "exp_month": token["exp_month"],
            "exp_year": token["exp_year"],
            "status": card["status"],
        }


@mcp.tool()
def vic_deprovision_token(v_provisioned_token_id: str) -> dict:
    """
    Deprovision (delete) a network token
    (VTS ``provisionedTokens/{id}/delete``, reason ``CUSTOMER_CONFIRMED``).

    Args:
        v_provisioned_token_id: The token to delete.
    """
    with _lock:
        token = _tokens.get(v_provisioned_token_id)
        if token is None:
            return {"success": False, "error": "Unknown vProvisionedTokenID."}
        token["status"] = TOKEN_DELETED
        _vic_cards.pop(v_provisioned_token_id, None)
        # Drop the user->card relationship if it points at this token.
        if token.get("user_id") and _user_cards.get(token["user_id"]) == v_provisioned_token_id:
            _user_cards.pop(token["user_id"], None)

    return {
        "success": True,
        "vProvisionedTokenID": v_provisioned_token_id,
        "tokenStatus": TOKEN_DELETED,
        "updateReason": "CUSTOMER_CONFIRMED",
        "deleted_at": _now_iso(),
    }


# ---------------------------------------------------------------------------
# VIC / VACP — agentic commerce (instruction + mandate -> credentials -> confirm)
# ---------------------------------------------------------------------------
@mcp.tool()
def vic_create_instruction(
    user_id: str,
    v_provisioned_token_id: str,
    amount: float,
    currency_code: str = "840",
    prompt: str = "",
    merchant_name: str = "Travel Concierge",
) -> dict:
    """
    Create a VIC **instruction** carrying a spending **mandate**
    (VIC ``/vacp/v1/instructions``). The mandate authorizes the agent to spend up
    to ``amount`` in ``currency_code`` until it expires (``effectiveUntilTime``).
    This is the consumer's delegated authorization for the agent to transact; it
    must exist and be ACTIVE before credentials can be retrieved.

    Args:
        user_id: The paying user.
        v_provisioned_token_id: The enrolled network token.
        amount: The mandate's ``declineThreshold`` (max total the agent may spend).
        currency_code: ISO 4217 numeric currency (e.g. "840" = USD).
        prompt: The shopping intent / compressed prompt describing the request.
        merchant_name: Merchant display name the mandate is scoped to.
    """
    with _lock:
        token = _tokens.get(v_provisioned_token_id)
        if token is None or token["status"] != TOKEN_ACTIVE:
            return {"success": False, "error": "Token is not active; enroll and provision a card first."}
        if v_provisioned_token_id not in _vic_cards:
            return {"success": False, "error": "Token is not enrolled for agentic commerce (call vic_enroll_card)."}

        instruction_id = f"VINS-{int(time.time())}-{_rand(8)}"
        mandate_id = "MAN-" + _rand(24, string.ascii_lowercase + string.digits)
        effective_until = datetime.now(timezone.utc) + timedelta(days=MANDATE_EFFECTIVE_DAYS)

        mandate = {
            "mandateId": mandate_id,
            "status": MANDATE_ACTIVE,
            "instruction_id": instruction_id,
            "declineThreshold": {"amount": round(float(amount), 2), "currencyCode": currency_code},
            "effectiveUntilTime": effective_until.isoformat(),
            "description": prompt or merchant_name,
            "spent": 0.0,
        }
        _mandates[mandate_id] = mandate
        _instructions[instruction_id] = {
            "instruction_id": instruction_id,
            "user_id": user_id,
            "token_id": v_provisioned_token_id,
            "mandate_id": mandate_id,
            "merchant_name": merchant_name,
            "status": INTENT_ACTIVE,
            "compressedPrompt": prompt,
        }

    return {
        "success": True,
        "instructionId": instruction_id,
        "status": INTENT_ACTIVE,
        "compressedPrompt": prompt,
        "mandate": {
            "mandateId": mandate_id,
            "status": MANDATE_ACTIVE,
            "declineThreshold": mandate["declineThreshold"],
            "effectiveUntilTime": mandate["effectiveUntilTime"],
        },
        "created_at": _now_iso(),
    }


@mcp.tool()
def vic_retrieve_credentials(
    instruction_id: str,
    v_provisioned_token_id: str,
    transactions: list[dict],
) -> dict:
    """
    Retrieve per-transaction payment **credentials** for an active instruction
    (VIC ``/vacp/v1/instructions/{id}/credentials``). Each requested transaction
    is checked against the instruction's mandate (spend ceiling + expiry). For
    each approved transaction a network cryptogram + DPAN + dCVV2 is returned;
    over-limit/expired requests are declined.

    Args:
        instruction_id: The ``instructionId`` from ``vic_create_instruction``.
        v_provisioned_token_id: The token being charged.
        transactions: List of ``{merchant_name, amount, currency_code?,
            merchant_url?, merchant_country_code?}`` items.
    """
    with _lock:
        instruction = _instructions.get(instruction_id)
        if instruction is None:
            return {"success": False, "status": "FAILED", "error": "Unknown instructionId."}
        if instruction["token_id"] != v_provisioned_token_id:
            return {"success": False, "status": "FAILED", "error": "Token does not match the instruction."}
        if instruction["status"] != INTENT_ACTIVE:
            return {"success": False, "status": "FAILED", "error": f"Instruction is {instruction['status']}."}

        mandate = _mandates.get(instruction["mandate_id"], {})
        threshold = float(mandate.get("declineThreshold", {}).get("amount", 0))
        expired = False
        try:
            expired = datetime.fromisoformat(mandate["effectiveUntilTime"]) < datetime.now(timezone.utc)
        except (KeyError, ValueError):
            expired = False

        approved: list[dict] = []
        declined: list[dict] = []
        running = float(mandate.get("spent", 0.0))

        for txn in transactions or []:
            amount = round(float(txn.get("amount", 0) or 0), 2)
            currency = str(txn.get("currency_code") or "840")
            merchant = txn.get("merchant_name") or instruction["merchant_name"]
            reference_id = f"VTXN-{int(time.time())}-{_rand(6)}"

            decline_reason = None
            if mandate.get("status") != MANDATE_ACTIVE or expired:
                decline_reason = "MANDATE_INACTIVE"
            elif amount <= 0:
                decline_reason = "INVALID_AMOUNT"
            elif amount >= HARD_DECLINE_CEILING:
                decline_reason = "AMOUNT_LIMIT_EXCEEDED"
            elif running + amount > threshold + 1e-9:
                decline_reason = "MANDATE_LIMIT_EXCEEDED"

            if decline_reason:
                declined.append({
                    "transactionReferenceId": reference_id,
                    "merchantName": merchant,
                    "amount": amount,
                    "declineReason": decline_reason,
                })
                continue

            running += amount
            seed = f"{instruction_id}:{reference_id}:{v_provisioned_token_id}"
            _transactions[reference_id] = {
                "instruction_id": instruction_id,
                "mandate_id": instruction["mandate_id"],
                "amount": amount,
                "currency_code": currency,
                "merchant_name": merchant,
                "merchant_url": txn.get("merchant_url", "https://www.example.com"),
                "merchant_country_code": txn.get("merchant_country_code", "US"),
                "status": TXN_ACTIVE,
            }
            approved.append({
                "transactionReferenceId": reference_id,
                "dynamicDataId": f"DDI-{_rand(16)}",
                "paymentToken": _dpan(seed),        # network token DPAN
                "dynamicDataValue": _rand(3, string.digits),  # dCVV2
                "tokenExpirationMonth": _tokens.get(v_provisioned_token_id, {}).get("exp_month", 12),
                "tokenExpirationYear": _tokens.get(v_provisioned_token_id, {}).get("exp_year", 2029),
                "cryptogram": _rand(28, string.ascii_uppercase + string.digits),
                "eci": "05",
                "merchantName": merchant,
                "amount": amount,
                "currencyCode": currency,
                "status": TXN_ACTIVE,
            })

        if approved:
            _mandates[instruction["mandate_id"]]["spent"] = running

    status = "COMPLETED" if approved and not declined else ("PARTIAL" if approved else "DECLINED")
    return {
        "success": bool(approved),
        "status": status,
        # In the real API these credentials arrive inside a signed JWT
        # (`signedPayload`); the mock exposes them directly for demo clarity.
        "signedPayload": f"mock.jws.{_rand(24, string.ascii_letters + string.digits)}",
        "credentials": approved,
        "declined": declined,
        "retrieved_at": _now_iso(),
    }


@mcp.tool()
def vic_confirm_transaction(
    instruction_id: str,
    transaction_reference_id: str,
    amount: float,
    currency_code: str = "840",
    transaction_status: str = TXN_STATUS_APPROVED,
    order_id: str = "",
) -> dict:
    """
    Confirm the outcome of a transaction back to VIC
    (VIC ``/vacp/v1/instructions/{id}/confirmations``). Reports whether the
    merchant approved or declined the payment so the mandate ledger reflects the
    final state. Call once per transaction after settlement.

    Args:
        instruction_id: The instruction the transaction belongs to.
        transaction_reference_id: The ``transactionReferenceId`` from credentials.
        amount: The settled amount.
        currency_code: ISO 4217 numeric currency (e.g. "840" = USD).
        transaction_status: "APPROVED" or "DECLINED".
        order_id: Optional merchant order id to associate.
    """
    with _lock:
        txn = _transactions.get(transaction_reference_id)
        if txn is None:
            return {"success": False, "error": "Unknown transactionReferenceId."}
        final = TXN_SUCCESS if str(transaction_status).upper() == TXN_STATUS_APPROVED else TXN_FAILURE
        txn["status"] = final
        if final == TXN_FAILURE:
            # Release the reserved amount from the mandate ledger on decline.
            mandate = _mandates.get(txn["mandate_id"])
            if mandate:
                mandate["spent"] = max(0.0, float(mandate.get("spent", 0.0)) - float(amount or 0))

    return {
        "success": final == TXN_SUCCESS,
        "instructionId": instruction_id,
        "transactionReferenceId": transaction_reference_id,
        "transactionType": TRANSACTION_TYPE_PURCHASE,
        "transactionStatus": final,
        "orderId": order_id or None,
        "amount": round(float(amount or 0), 2),
        "currencyCode": currency_code,
        "confirmed_at": _now_iso(),
    }


@mcp.tool()
def vic_health() -> dict:
    """Simple health/identity probe for the mock VIC server."""
    return {"service": "vic-mock-mcp", "status": "ok", "mode": "mock"}


if __name__ == "__main__":
    logger.info("Starting Mock VIC MCP server on :%s/mcp", PORT)
    mcp.run(transport="streamable-http")
