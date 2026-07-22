---
name: hotel-booking
description: Find and compare lodging — hotels, resorts and rentals — with area, nightly price, rating and Bing Maps links. Use whenever the traveler asks about where to stay, hotels, accommodation, or when a trip plan needs lodging.
---

# Hotel Booking skill

Find and compare places to stay and hand a shortlist back for the itinerary.

## Tools to use

Use the **WebIQ** web-intelligence tools directly for real lodging data — call
them by name (no discovery step):

1. **`web`** — search for current properties and prices, e.g.
   `mid-range hotels Shinjuku Tokyo October 2025 under 200 USD`.
2. **`browse`** — open a listing to read specifics (nightly price, rating, address).
3. **`places`** — look up the hotel on the map to get its **exact name and street
   address** (and coordinates). Use this so every Bing Maps link points at the real
   property, not just a city search.

Only if WebIQ itself fails to connect should you fall back to the built-in
**web search** tool. Do not fabricate properties or prices — look them up.

A tool call awaiting a one-time human approval is **normal HITL behavior, not an
error**. Do not call WebIQ "unavailable" or fall back to web search just because an
approval is pending — wait for it, then proceed.

## Method

1. **Understand the stay.** Destination/area, check-in and check-out dates, number
   of guests, budget/price range and any traveler preferences (neighborhood,
   amenities, star rating). Infer from the itinerary where possible.
2. **Search.** Query the WebIQ `web`/`browse` tools for suitable properties, and
   use `places` to confirm each property's exact name and address.
3. **Shortlist.** Present a **3–5** property shortlist. For each property include:
   name, neighborhood/area, approximate nightly price, guest rating, and a **Bing
   Maps** link. ALWAYS include a Bing Maps link for every property — build it as
   `https://www.bing.com/maps?q=<url-encoded hotel name and address>` using the
   address from `places`; if you only have the name and city, still produce a link
   from those. Never omit the map link.
4. **Hand back.** Do **not** book or purchase — the checkout skill handles that.
   Summarize the recommended property so the concierge can save it to the active
   itinerary as a `hotel` item (hotels are bookable at checkout).

## Output

Keep it simple (ELI5): a short shortlist, one line per hotel (name, area, price/night,
rating, Bing Maps link). No long intros. End with one line: your top pick and why
(≤1 sentence). Every property MUST carry a Bing Maps link — no exceptions.
