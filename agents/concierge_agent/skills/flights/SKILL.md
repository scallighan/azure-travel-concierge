---
name: flights
description: Search and compare real flight options — routes, airlines, schedules, fares and booking guidance — and present a numbered shortlist the traveler can pick from. Use whenever the traveler asks about flights, airfare, or getting between places by air, or when a trip plan needs air travel.
---

# Flights skill

Find real, current flight options and present them as a **numbered shortlist the
traveler selects from**, then hand the chosen flight back to be saved to the
itinerary.

## Tools to use

Use the **travel-concierge-toolbox** for real-world flight data. The toolbox
exposes a discovery interface, not one tool per site:

1. Call **`tool_search`** with a broad query like `web`, `webiq`, or `search`
   to find the web-intelligence tools (do **not** search for `flights` or
   `airline` — those return "no tools matched", which is expected and does **not**
   mean the toolbox is down).
2. Use **`webiq___web`** (query search) to find current routes, airlines and fares,
   e.g. `nonstop flights ORD to HND October 2025 economy`.
3. Use **`webiq___browse`** (URL fetch) to open an airline or aggregator page and
   read specific flight numbers, times and prices.

Only if the toolbox itself fails to connect should you fall back to the built-in
**web search** tool. **Never invent fares or flight numbers — always look them up.**

### A pending approval is not a failure

Loading this skill or calling a tool may require a one-time human approval. A tool
call that is awaiting approval is **normal HITL behavior, not an error**. Do **not**
describe the toolbox or skill loader as "unavailable" and do **not** silently fall
back to web search because an approval is pending — wait for the approval, then
proceed with the toolbox.

## Method

1. **Confirm the essentials.** Origin, destination, travel dates and cabin class.
   Only ask the user for a missing detail if you genuinely cannot infer it from the
   conversation or their itinerary. Use `YYYY-MM-DD` dates and 3-letter IATA airport
   codes internally.
2. **Search for real options.** Query WebIQ across a couple of angles (nonstop vs.
   connecting, nearby airports if helpful). Prefer nonstop when the traveler asked
   for it. Pull actual airline, flight numbers, times and fares — browse a page when
   you need specifics.
3. **Present a numbered, selectable shortlist.** Show **2–4** real options as a
   numbered list (1, 2, 3…), each with: airline **and flight number(s)**,
   departure/arrival airports and local times, number of stops (and layover if
   connecting), approximate fare, and a booking link when available. End by asking
   the traveler to reply with the number of the flight they want (or ask for
   different options).
4. **Hand back the selection.** Do **not** purchase anything — purchasing is the
   checkout skill's job. Once the traveler picks a numbered option, summarize that
   specific flight so the concierge can save it to the active itinerary as a
   `flight` item (flights are bookable at checkout).

## Output

A concise, **numbered** list of real flight options the user can choose from. Lead
with your recommended pick and one sentence on why, then invite the traveler to
select by number.
