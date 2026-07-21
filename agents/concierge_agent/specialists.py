"""
Specialist "skills" for the harness supervisor: Flights, Hotel Booking and
Food & Entertainment. Each is a lightweight sub-agent that consumes the Foundry
Toolbox (WebIQ web-intelligence tools) and is exposed to the supervisor as a
callable tool. When no Toolbox is configured they fall back to the built-in
Foundry web-search tool.
"""

import logging

from prompts import (
    FLIGHTS_SKILL_PROMPT,
    FOOD_ENTERTAINMENT_SKILL_PROMPT,
    HOTEL_SKILL_PROMPT,
)

logger = logging.getLogger("specialists")


def _skill(client, name, instructions, tools, description):
    agent = client.as_agent(name=name, instructions=instructions, tools=[t for t in tools if t])
    return agent.as_tool(
        name=name,
        description=description,
        arg_name="query",
        arg_description="The request in natural language, always including the user's id and any dates/locations.",
    )


def build_specialist_tools(client, *, skill_tools: list) -> list:
    """Return the Flights, Hotel Booking and Food & Entertainment skill tools.

    ``skill_tools`` is the list of tools the skills share — the Foundry Toolbox
    MCP tool when configured, otherwise the built-in Foundry web-search tool.
    """
    shared = [t for t in skill_tools if t]
    return [
        _skill(
            client,
            "flights_skill",
            FLIGHTS_SKILL_PROMPT,
            shared,
            "Look up flight options, schedules, fares and routes for a trip.",
        ),
        _skill(
            client,
            "hotel_booking_skill",
            HOTEL_SKILL_PROMPT,
            shared,
            "Find and compare hotels and lodging for a trip, with Bing Maps links.",
        ),
        _skill(
            client,
            "food_entertainment_skill",
            FOOD_ENTERTAINMENT_SKILL_PROMPT,
            shared,
            "Recommend restaurants, food experiences, attractions and things to do.",
        ),
    ]
