---
name: maps
description: Look up where a place is — its exact name, address, coordinates and a Bing Maps link — and answer location/proximity questions like "restaurants near my hotel", "what's around the hotel", or "how far is the museum". Read-only; nothing is booked. Use whenever the traveler asks where something is, for directions/distance, a map link, or things near a place on their itinerary.
---

# Maps skill

Answer "where is it / what's near it" questions with accurate location info and a
Bing Maps link for every place. This skill is **read-only** — it never books,
carts, or checks out anything.

## Tools to use

Use the **WebIQ** web-intelligence tools directly:

- **`places`** — the primary tool. Look up a place to get its **exact name,
  street address and coordinates**. Also use it for "near" / proximity searches
  (e.g. restaurants near a hotel address).
- **`web`** / **`browse`** — for supporting detail (hours, "top X near Y" lists,
  neighborhood context) when `places` alone isn't enough.

Only if WebIQ fails to connect, fall back to the built-in **web search** tool.
Never invent addresses, coordinates or distances — look them up.

## Method

1. **Find the anchor.** Identify the place the question is about. For "near my
   hotel"-style questions, use the hotel already on the active itinerary (its
   name/location) as the anchor — don't re-ask if it's known. If no anchor place
   is known, ask the user for one (city or address) in one short line.
2. **Resolve exact location.** Call `places` to confirm the anchor's exact name
   and street address (and coordinates).
3. **Search nearby (if asked).** For proximity questions, use `places` around the
   anchor's address to find the requested category (restaurants, coffee, sights,
   pharmacy…). Keep it to the **top 3–5** closest/best matches.
4. **Build map links.** For the anchor and every result, produce a **Bing Maps**
   link: `https://www.bing.com/maps?q=<url-encoded name and address>`. For a
   "near" question you may also give a single search link centered on the anchor:
   `https://www.bing.com/maps?q=<category>%20near%20<url-encoded address>`.
5. **Hand back.** If any nearby place is a restaurant/attraction the user may want
   on their trip, the concierge can save it to the itinerary as an `activity`
   item (with its `map_url`) — but this skill itself books nothing.

## Output

Keep it simple (ELI5). One line per place: **name — one short locator detail
(neighborhood or distance) — Bing Maps link**. Lead with the anchor, then the
nearby list. No long intros. Every place MUST carry a Bing Maps link — no
exceptions.
