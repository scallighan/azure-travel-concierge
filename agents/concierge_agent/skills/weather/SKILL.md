---
name: weather
description: Get the estimated weather forecast for the trip — a day-by-day table of the expected conditions for the traveler's itinerary dates and destination(s). Reads the dates and places already on the active itinerary so the user doesn't have to repeat them. Read-only; nothing is booked. Use whenever the traveler asks about weather, temperature, rain, what to pack, or "what will it be like when I'm there".
---

# Weather skill

Tell the traveler what the weather is expected to be for **their trip** — the
specific dates and destination already on the itinerary — as a clean day-by-day
table. This skill is **read-only**: it never books, carts, or checks out anything.

## Tools to use

Use the **WebIQ** web-intelligence tools directly for real, current forecast data —
call them by name (no discovery step):

1. **`web`** — the primary tool. Search for the current forecast for the
   destination and dates, e.g. `Tokyo weather forecast October 20-25 2026` or
   `10 day forecast Kyoto`.
2. **`browse`** — open a specific forecast page (a national weather service or a
   reputable forecaster) to read the per-day highs, lows and conditions.

Only if WebIQ itself fails to connect should you fall back to the built-in
**web search** tool. **Never invent temperatures or conditions — always look them
up.**

### A pending approval is not a failure

Calling a tool may require a one-time human approval. A tool call that is awaiting
approval is **normal HITL behavior, not an error**. Do **not** describe WebIQ or the
skill loader as "unavailable" and do **not** silently fall back to web search because
an approval is pending — wait for the approval, then proceed.

## Method

1. **Read the trip from the itinerary.** Get the destination(s) and the travel
   **dates** from the active itinerary — the flight/hotel dates and any city on the
   plan. Do **not** re-ask the user for dates or destination if they are already
   known. If the itinerary has no dates or destination yet, ask the user for the
   city and dates in one short line.
2. **Handle the forecast horizon honestly.** Real forecasts only reach ~10–14 days
   out. If the trip is within that window, use the **actual forecast**. If it is
   further out, use **typical/seasonal averages** for those dates (climate normals)
   and clearly label the table as *typical for the season*, not a live forecast.
3. **Look up the weather.** Use `web` (and `browse` for specifics) to pull the
   per-day forecast or the seasonal averages for the destination across the trip
   dates. For multi-city trips, get the weather for each city on its relevant days.
4. **Build a day-by-day table.** One row per trip day with the date, the place, the
   high/low temperature and a short conditions summary (and precipitation chance
   when available). Cover every day of the trip.
5. **Hand back.** Add a one-line packing tip based on the outlook (e.g. "pack a
   light rain jacket"). This skill saves nothing to the itinerary and books
   nothing.

## Output

Keep it simple (ELI5). Lead with one short sentence naming the destination and date
range, then a **Markdown table** with these columns:

| Date | Place | High / Low | Conditions | Rain |
| ---- | ----- | ---------- | ---------- | ---- |

One row per trip day, in date order. Show temperatures in the units that suit the
destination (note °C/°F). If you used seasonal averages instead of a live forecast,
say so in the lead line. Finish with a single short packing tip. No long intros.
