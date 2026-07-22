# Merchant Mock MCP server

A self-contained **mock merchant / acquirer** for the Travel Concierge demo. It
plays the *merchant* role in the Visa Intelligent Commerce (VIC) agentic-commerce
flow — the party that is **separate from Visa (VDP)** and actually settles the
sale.

In VIC, the agent:

1. gets a spending **mandate** and retrieves per-transaction network-token
   **credentials** from Visa (`vic-mock` in this repo), then
2. **presents those credentials to the merchant**, who authorizes/settles the
   charge with the network and creates the order.

This service is step 2. It never sees the card PAN — only the network token
(DPAN) + cryptogram from the VIC credentials.

Mirrors `reference-merchant-backend` / `reference-merchant-mcp` in
[visa/vic-reference-agent](https://github.com/visa/vic-reference-agent). It keeps
**no product catalog** (the travel domain lives in `travel-tools`) — only the
settlement / order boundary.

## Tools

| Tool | Purpose |
|------|---------|
| `merchant_authorize(amount, payment_credentials, currency_code?, order_reference?, merchant_name?, items?)` | Validate VIC credentials, approve/decline, create the order, return an authorization code + merchant order id. Idempotent per `transactionReferenceId`. |
| `merchant_get_order(order_id)` | Look up a previously authorized order. |
| `merchant_health()` | Liveness/readiness probe. |

## Where it sits in checkout

```
cart-tools.cart_confirm_purchase
  ├─ vic_create_instruction     (vic-mock)  → instruction + spending mandate
  ├─ vic_retrieve_credentials   (vic-mock)  → network-token credentials
  ├─ merchant_authorize         (this)      → settle + create merchant order   ← NEW boundary
  └─ vic_confirm_transaction    (vic-mock)  → confirm outcome back to Visa
```

## Configuration

| Env | Default | Meaning |
|-----|---------|---------|
| `PORT` | `8080` | HTTP port; MCP is served at `/mcp`. |
| `MERCHANT_NAME` | `Travel Concierge` | Display name on orders. |
| `MERCHANT_DECLINE_CEILING` | `100000` | Amounts at/above this are declined by the mock acquirer. |

## Run locally

```bash
pip install -r requirements.txt
python server.py            # serves MCP streamable-http on :8080/mcp
```

> **Note:** this is a **mock** for demonstration only — it performs no real
> authorization, cryptography or settlement, and keeps orders in memory (run a
> single replica).
