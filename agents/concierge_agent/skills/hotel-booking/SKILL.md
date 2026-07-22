---
name: hotel-booking
description: Find and compare lodging — hotels, resorts and rentals — with area, nightly price, rating and Bing Maps links. Use whenever the traveler asks about where to stay, hotels, accommodation, or when a trip plan needs lodging.
---

# Hotel Booking skill

Find and compare places to stay and hand a shortlist back for the itinerary.

## Tools to use

Use the **travel-concierge-toolbox** for real lodging data. The toolbox exposes a
discovery interface, not one tool per site:

1. Call **`tool_search`** with a broad query like `web`, `webiq`, or `search` to
   find the web-intelligence tools (do **not** search for `hotel` or `lodging` —
   those return "no tools matched", which is expected and does **not** mean the
   toolbox is down).
2. Use **`webiq___web`** to find current properties and prices, then
   **`webiq___browse`** to open a listing and read specifics.

Only if the toolbox itself fails to connect should you fall back to the built-in
**web search** tool. Do not fabricate properties or prices — look them up.

A tool call awaiting a one-time human approval is **normal HITL behavior, not an
error**. Do not call the toolbox "unavailable" or fall back to web search just
because an approval is pending — wait for it, then proceed.

## Method

1. **Understand the stay.** Destination/area, check-in and check-out dates, number
   of guests, budget/price range and any traveler preferences (neighborhood,
   amenities, star rating). Infer from the itinerary where possible.
2. **Search.** Query the toolbox / web tools for suitable properties.
3. **Shortlist.** Present a **3–5** property shortlist. For each property include:
   name, neighborhood/area, approximate nightly price, guest rating, and a **Bing
   Maps** link (`https://www.bing.com/maps?q=<url-encoded name and address>`).
4. **Hand back.** Do **not** book or purchase — the checkout skill handles that.
   Summarize the recommended property so the concierge can save it to the active
   itinerary as a `hotel` item (hotels are bookable at checkout).

## Output

A concise, structured shortlist. Lead with your recommended pick and one sentence
on why. Every property must carry a Bing Maps link.
