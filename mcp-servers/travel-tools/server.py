"""
Travel Tools MCP Server
=======================

Exposes raw travel tools over MCP (streamable-http). No agent logic here — just
tool implementations that the travel sub-agent orchestrates.

Optional API keys (SERP_API_KEY, GOOGLE_MAPS_KEY, ...) are hydrated from Azure
Key Vault when ``KEY_VAULT_URI`` is set; otherwise the tools return deterministic
mock data so the demo runs with no external dependencies.
"""

import logging
import os
from typing import Optional

from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("travel-tools-mcp")

PORT = int(os.getenv("PORT", "8080"))


def _load_keys_from_keyvault() -> None:
    kv_uri = os.getenv("KEY_VAULT_URI")
    if not kv_uri:
        logger.info("No KEY_VAULT_URI set — travel tools run in mock mode.")
        return
    try:
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient

        client = SecretClient(vault_url=kv_uri, credential=DefaultAzureCredential())
        # secret-name -> env-var
        wanted = {
            "serp-api-key": "SERP_API_KEY",
            "google-maps-key": "GOOGLE_MAPS_KEY",
            "openweather-api-key": "OPENWEATHER_API_KEY",
        }
        for secret_name, env_var in wanted.items():
            if os.getenv(env_var):
                continue
            try:
                os.environ[env_var] = client.get_secret(secret_name).value
                logger.info("Loaded %s from Key Vault", env_var)
            except Exception:
                logger.info("Secret %s not present — %s stays in mock mode", secret_name, env_var)
    except Exception as exc:  # pragma: no cover
        logger.warning("Key Vault unavailable (%s) — using mock travel data", exc)


_load_keys_from_keyvault()

from tools import (  # noqa: E402
    flight_search,
    hotel_search,
    places_search,
    search_tool,
)

mcp = FastMCP("Travel Tools", host="0.0.0.0", port=PORT, stateless_http=True)


@mcp.tool()
def travel_search(query: str) -> str:
    """
    Search the internet for travel information (destinations, tips, weather).

    Args:
        query: e.g. "best restaurants in Rome", "weather in Tokyo in December".
    """
    return search_tool(query)


@mcp.tool()
def travel_places_search(query: str) -> dict:
    """
    Find restaurants, attractions and points of interest with Bing Maps links.

    Args:
        query: e.g. "museums near the Eiffel Tower", "sushi in Tokyo".
    """
    return places_search(query)


@mcp.tool()
def travel_hotel_search(query: str, check_in_date: str, check_out_date: str) -> str:
    """
    Search hotels for a city and date range.

    Args:
        query: e.g. "boutique hotels in Paris".
        check_in_date: YYYY-MM-DD.
        check_out_date: YYYY-MM-DD.
    """
    return hotel_search(query, check_in_date, check_out_date)


@mcp.tool()
def travel_flight_search(
    departure_id: str,
    arrival_id: str,
    outbound_date: str,
    return_date: Optional[str] = None,
) -> str:
    """
    Search flights between two airports.

    Args:
        departure_id: Departure airport IATA code (e.g. "JFK").
        arrival_id: Arrival airport IATA code (e.g. "CDG").
        outbound_date: YYYY-MM-DD.
        return_date: Optional YYYY-MM-DD for round trips.
    """
    return flight_search(departure_id, arrival_id, outbound_date, return_date)


if __name__ == "__main__":
    logger.info("Starting Travel Tools MCP server on :%s/mcp", PORT)
    mcp.run(transport="streamable-http")
