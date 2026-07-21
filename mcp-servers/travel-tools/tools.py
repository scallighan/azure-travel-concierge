"""
Travel tool implementations.

By default these return deterministic, realistic-looking **mock** data so the
demo works with zero external API keys. If the corresponding key is present as
an environment variable (optionally hydrated from Key Vault by ``server.py``),
the ``_real_*`` hooks can be filled in to call the live provider (SerpAPI,
Google Places, Azure Maps, Bing Search, etc.).
"""

import hashlib
import os
from datetime import date, datetime, timedelta


def _seeded(seed: str, lo: int, hi: int) -> int:
    h = int(hashlib.sha256(seed.encode()).hexdigest(), 16)
    return lo + (h % (hi - lo + 1))


def _maps_link(name: str, city: str = "") -> str:
    q = f"{name},{city}".strip(",").replace(" ", "+")
    return f"https://www.bing.com/maps?q={q}"


# ---------------------------------------------------------------------------
# Internet / travel info search
# ---------------------------------------------------------------------------
def search_tool(query: str) -> str:
    if os.getenv("SERP_API_KEY"):
        real = _real_search(query)
        if real:
            return real

    topics = [
        ("Top experiences", "curated highlights loved by recent travellers"),
        ("Best time to visit", "shoulder-season months offer good weather and fewer crowds"),
        ("Getting around", "public transit and rideshare are widely available"),
        ("Local tips", "carry a little cash; many cafes are card-friendly but markets are not"),
    ]
    lines = [f"Search results for: {query}", ""]
    for i, (title, body) in enumerate(topics, 1):
        lines.append(f"{i}. {title} — {body}. (source: travel-guide.example/{i})")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Places / restaurants / attractions
# ---------------------------------------------------------------------------
def places_search(query: str) -> dict:
    if os.getenv("GOOGLE_MAPS_KEY"):
        real = _real_places(query)
        if real:
            return real

    city = query.split(" in ")[-1] if " in " in query else ""
    base_names = [
        "Old Town Bistro", "Harbor View Cafe", "Museum of Modern Art",
        "Central Market Hall", "Rooftop Garden Bar", "Riverside Walk",
    ]
    results = []
    for i, name in enumerate(base_names[:5]):
        rating = round(3.8 + (_seeded(query + name, 0, 12) / 10), 1)
        results.append({
            "name": name,
            "address": f"{_seeded(name, 1, 200)} Main St, {city or 'City Center'}",
            "rating": min(rating, 5.0),
            "user_ratings_total": _seeded(name + "rt", 40, 4200),
            "maps_link": _maps_link(name, city),
            "types": ["restaurant" if i % 2 == 0 else "tourist_attraction"],
        })
    return {"query": query, "results": results, "source": "mock"}


# ---------------------------------------------------------------------------
# Hotels
# ---------------------------------------------------------------------------
def hotel_search(query: str, check_in_date: str, check_out_date: str) -> str:
    try:
        nights = max((date.fromisoformat(check_out_date) - date.fromisoformat(check_in_date)).days, 1)
    except Exception:
        nights = 1

    city = query.split(" in ")[-1] if " in " in query else query
    names = ["Grand Central Hotel", "The Boutique Loft", "Riverside Suites", "Skyline Resort"]
    lines = [f"Hotels for '{query}' ({check_in_date} → {check_out_date}, {nights} night(s)):", ""]
    for i, name in enumerate(names, 1):
        price = _seeded(name + check_in_date, 120, 480)
        stars = _seeded(name, 3, 5)
        hotel_id = f"HOT-{hashlib.sha1(name.encode()).hexdigest()[:8].upper()}"
        lines.append(
            f"{i}. {name} ({stars}★) — ${price}/night, total ${price * nights}\n"
            f"   id={hotel_id} city={city} amenities=WIFI,POOL,GYM\n"
            f"   {_maps_link(name, city)}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Flights
# ---------------------------------------------------------------------------
def flight_search(departure_id: str, arrival_id: str, outbound_date: str, return_date: str | None = None) -> str:
    airlines = ["Contoso Air", "Fabrikam Airways", "Northwind Jet"]
    lines = [f"Flights {departure_id.upper()} → {arrival_id.upper()} on {outbound_date}"]
    if return_date:
        lines[0] += f" (return {return_date})"
    lines.append("")
    for i, airline in enumerate(airlines, 1):
        price = _seeded(airline + outbound_date + departure_id, 180, 720)
        dur_h = _seeded(airline + arrival_id, 2, 11)
        stops = 0 if i == 1 else _seeded(airline + "s", 0, 1)
        flight_id = f"FL-{hashlib.sha1((airline+outbound_date).encode()).hexdigest()[:8].upper()}"
        lines.append(
            f"{i}. {airline} — ${price} {'roundtrip' if return_date else 'one-way'}\n"
            f"   id={flight_id} {departure_id.upper()}→{arrival_id.upper()} "
            f"duration {dur_h}h, {'nonstop' if stops == 0 else f'{stops} stop'}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Real-provider hooks (fill in to go live)
# ---------------------------------------------------------------------------
def _real_search(query: str):  # pragma: no cover - demo stub
    return None


def _real_places(query: str):  # pragma: no cover - demo stub
    return None
