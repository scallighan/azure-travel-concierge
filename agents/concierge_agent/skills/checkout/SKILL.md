---
name: checkout
description: Complete a purchase the traveler has explicitly confirmed (flights, hotels, tickets) through the secure payments agent. Use only after the user confirms exactly what to buy; never handle card details in chat.
---

# Checkout skill

Turn a confirmed selection into a completed purchase — safely — by delegating to
the secure **payments agent** (`payments_agent` tool), which talks to the payment
provider (Visa Intelligent Commerce, VIC). This skill is about the *workflow and
guardrails*; the actual payment is executed by the payments agent tool.

## How VIC payments work (context)

VIC is Visa's agentic-commerce platform. A card is onboarded once (PAN enrolled
with VTS, a network token provisioned and enrolled for agentic commerce). Each
purchase runs under a **mandate** — a spending authorization (max amount, limited
validity) the user delegates to the agent. The payments agent creates an
instruction under that mandate, retrieves per-transaction credentials (a network
token, never the real card), and confirms the outcome. A purchase that would
exceed the mandate is declined.

## Absolute payment safety rules

- **NEVER** ask for, accept, or repeat a card number, CVV or expiration in chat.
  Card entry happens only through the secure card flow surfaced by the UI.
- Only start checkout **after the user has explicitly confirmed** what they want to
  buy (item, price, dates).
- Do all purchasing through the `payments_agent` tool — never simulate a purchase
  yourself.

## Method

1. **Confirm the order.** Restate exactly what will be purchased (item, price,
   date) and get an explicit "yes".
2. **Delegate to payments.** Call the `payments_agent` tool with the user's id and
   a clear description of the confirmed purchase. The payments agent will:
   - check whether the user has a payment card on file (if not, it will tell the
     user to add one securely via the UI — relay that and stop);
   - complete the purchase under a mandate and return an order id / total, or a
     decline reason (e.g. the amount exceeded the spending mandate).
3. **Report back.** Relay the order id, total and outcome clearly and concisely,
   and update the active itinerary (via `save_itinerary`) to reflect the booked
   item. If declined, relay the reason plainly.

## Output

A short confirmation with the order id and total, or a clear next step (e.g. "add a
card to continue" or a decline reason). Never expose card data.
