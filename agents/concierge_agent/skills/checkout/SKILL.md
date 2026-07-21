---
name: checkout
description: Complete a purchase the traveler has explicitly confirmed (flights, hotels, tickets) through the secure payments agent. Use only after the user confirms exactly what to buy; never handle card details in chat.
---

# Checkout skill

Turn a confirmed selection into a completed purchase — safely — by delegating to
the secure **payments agent** (`payments_agent` tool), which talks to the payment
provider (VIC). This skill is about the *workflow and guardrails*; the actual
payment is executed by the payments agent tool.

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
   - complete the purchase and return an order id / total.
3. **Report back.** Relay the order id, total and outcome clearly and concisely,
   and update the active itinerary (via `save_itinerary`) to reflect the booked
   item.

## Output

A short confirmation with the order id and total, or a clear next step (e.g. "add a
card to continue"). Never expose card data.
