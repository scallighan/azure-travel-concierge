---
name: flights
description: Search and compare real flight options — routes, airlines, schedules, fares and booking guidance — and present a numbered shortlist the traveler can pick from. Use whenever the traveler asks about flights, airfare, or getting between places by air, or when a trip plan needs air travel.
---

# Flights skill

Find real, current flight options and present them as a **numbered shortlist the
traveler selects from**, then hand the chosen flight back to be saved to the
itinerary.

## Tools to use

Use the **WebIQ** web-intelligence tools directly for real-world flight data —
call them by name (no discovery step):

1. **`web`** — search for current routes, airlines and fares, e.g.
   `nonstop flights ORD to HND October 2025 economy`.
2. **`browse`** — open an airline or aggregator page to read specific flight
   numbers, departure/arrival times and prices.

Only if WebIQ itself fails to connect should you fall back to the built-in
**web search** tool. **Never invent fares or flight numbers — always look them up.**

### A pending approval is not a failure

Calling a tool may require a one-time human approval. A tool call that is awaiting
approval is **normal HITL behavior, not an error**. Do **not** describe WebIQ or the
skill loader as "unavailable" and do **not** silently fall back to web search because
an approval is pending — wait for the approval, then proceed.

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
   numbered list (1, 2, 3…). Each option MUST show: airline **and flight number(s)**,
   **departure time**, **arrival time** (with airports; note +1 day if it lands the
   next day), number of stops (and layover if connecting), and the **cost/fare**. Add
   a booking link when available. End by asking the traveler to reply with the number
   of the flight they want (or ask for different options).
4. **Hand back the selection.** Do **not** purchase anything — purchasing is the
   checkout skill's job. Once the traveler picks a numbered option, summarize that
   specific flight so the concierge can save it to the active itinerary as a
   `flight` item (flights are bookable at checkout).

## Output

Keep it simple (ELI5): a short **numbered** list, one line per flight. Each line MUST
include the **departure time**, the **arrival time**, and the **cost** (plus airline +
flight no. and stops). No long intros. End with one line: your top pick and why
(≤1 sentence), then "Reply with the number you want."
