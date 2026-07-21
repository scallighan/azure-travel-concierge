---
name: flights
description: Search and compare flight options — routes, airlines, schedules, typical fares and booking guidance. Use whenever the traveler asks about flights, airfare, or getting between places by air, or when a trip plan needs air travel.
---

# Flights skill

Help the traveler find suitable flights and hand a clear shortlist back so it can
be added to their itinerary.

## Tools to use

Use the **travel-concierge-toolbox** tools (WebIQ web intelligence) when they are
available to look up current, real-world flight information. If the toolbox is not
available, fall back to the built-in **web search** tool. Never invent fares or
flight numbers — look them up.

## Method

1. **Confirm the essentials.** Origin, destination, travel dates and cabin class.
   Only ask the user for a missing detail if you genuinely cannot infer it from the
   conversation or their itinerary. Use `YYYY-MM-DD` dates and 3-letter IATA airport
   codes internally.
2. **Search.** Query the toolbox / web tools for current options across a couple of
   angles (nonstop vs. connecting, nearby airports if helpful).
3. **Shortlist.** Present **2–4** options, each with: airline, departure/arrival
   times, number of stops, approximate fare, and a booking link when available.
4. **Hand back.** Do **not** purchase anything — purchasing is the checkout skill's
   job. Summarize the recommended option so the concierge can save it to the active
   itinerary.

## Output

A concise, structured list of flight options. Lead with your recommended pick and
one sentence on why.
