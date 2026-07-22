---
name: food-entertainment
description: Recommend restaurants, food experiences, attractions and things to do at a destination, each with a Bing Maps link. These are saved to the itinerary as non-booked activities. Use whenever the traveler asks about food, dining, nightlife, activities, sightseeing or things to do.
---

# Food & Entertainment skill

Recommend where to eat and what to do, tailored to the destination and the
traveler's interests, and hand suggestions back for the itinerary. **These are
non-booked activities** — unlike flights and hotels, food & entertainment are
never purchased or checked out; they are simply added to the itinerary as
`activity` items for the traveler to enjoy on their own.

## Tools to use

Use the **travel-concierge-toolbox** tools (WebIQ web intelligence) when available
to find current restaurants, attractions and events; otherwise fall back to the
built-in **web search** tool. Do not invent venues — look them up.

## Method

1. **Understand the trip.** Destination, dates, and traveler interests (cuisine,
   budget, family-friendly, nightlife, culture, outdoors). Infer from the itinerary
   where possible.
2. **Search.** Query the toolbox / web tools across dining and activities.
3. **Recommend.** For a multi-day trip, suggest **2–3 dining options per day** plus
   notable attractions/experiences. For each item include: name, category
   (restaurant / attraction / activity), price level, a one-line why, and a **Bing
   Maps** link (`https://www.bing.com/maps?q=<url-encoded name and address>`).
4. **Hand back.** These are **activities, not bookings** — never purchase, add to
   the cart, or send them to checkout/`payments_agent`. Summarize picks so the
   concierge can save them to the active itinerary as `activity` items.

## Output

A concise, structured list grouped by day (when applicable). Every place must carry
a Bing Maps link.
