---
name: checkout
description: Complete a purchase the traveler has explicitly confirmed (flights and hotels only) through the secure payments agent. Use only after the user confirms exactly what to buy; never handle card details in chat.
---

# Checkout skill

Turn a confirmed **flight or hotel** selection into a completed (mock) purchase —
safely — by delegating to the secure **payments agent** (`payments_agent` tool),
which talks to the payment provider (Visa Intelligent Commerce, VIC). This skill
is about the *workflow and guardrails*; the actual payment is executed by the
payments agent tool.

## What can be checked out

- **Only flights and hotels are booked.** These are the sole purchasable items.
- **Food & entertainment are never checked out.** Restaurants, attractions and
  activities are planned suggestions saved to the itinerary as `activity` items,
  not purchases. Never send them to `payments_agent`. If the user asks to "book"
  a restaurant or activity, explain that those are added to the itinerary as
  activities and aren't booked here.

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
   date) and get an explicit "yes". **The price the user confirms IS the amount to
   charge** — the estimated flight/hotel prices you already have are the booking
   totals. There is no separate "trip system" or live-pricing service that returns
   exact totals; do NOT wait for, ask for, or block on "final"/"live" totals. Add
   up the confirmed item prices (e.g. nightly rate × nights, fare × travelers) and
   use that number.
2. **Verify a card is on file.** Call the `check_payment_card` tool with the user's
   id BEFORE any purchase. If it reports **no card on file**, tell the user they
   need to add a payment card — ask them to click **"Add card"** in the payment
   panel to add one securely — and **STOP** (do not call `payments_agent`). Once
   they confirm a card is added, re-run this check and continue.
3. **Delegate to payments.** With a card confirmed, call the `payments_agent` tool
   with the user's id, the active **itinerary_id**, a clear description of the
   confirmed purchase, AND the concrete total amount (a specific number in USD).
   Passing the itinerary_id lets the completed purchase be recorded as an order.
   The payments agent will:
   - complete the purchase under a mandate and return an order id / total, or a
     decline reason (e.g. the amount exceeded the spending mandate).
4. **Report back.** Confirm the booking as an **itemized list** (see Output),
   then update the active itinerary (via `save_itinerary`) to reflect the booked
   item(s). If declined, relay the reason plainly.

## Output

On success, show an **itemized order confirmation** (ELI5 — clean, no fluff):
- One line per booked item: the item name + key detail (e.g. flight route/date or
  hotel + nights) and its price.
- A **Total** line summing the items.
- The **order id**.

Prefer a small markdown table with `Item` / `Details` / `Price` columns (add a
final Total row), or a tight bulleted list if only one item. Example:

| Item | Details | Price |
| --- | --- | --- |
| Flight | ORD ↔ NRT nonstop, 2 travelers | $1,480 |
| Hotel | Hotel Sunroute Plaza Shinjuku, 4 nights | $860 |
| **Total** |  | **$2,340** |

Order id: `ORD-1234`

If a card is missing or the payment is declined, skip the table and give one clear
next step (e.g. "Add a card to continue" or a plain decline reason). Never
expose card data.
