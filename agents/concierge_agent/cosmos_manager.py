"""
Cosmos DB access for the supervisor: itinerary management + user-profile lookup.
Entra ID data-plane auth (async DefaultAzureCredential).
"""

import logging
import uuid
from datetime import datetime, timezone

from azure.cosmos.aio import CosmosClient
from azure.identity.aio import DefaultAzureCredential

from config import config

logger = logging.getLogger("agent-cosmos")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CosmosManager:
    def __init__(self) -> None:
        self._credential = DefaultAzureCredential()
        self._client = CosmosClient(config.COSMOS_ENDPOINT, credential=self._credential)
        self._db = self._client.get_database_client(config.COSMOS_DATABASE)
        self.itinerary = self._db.get_container_client("itinerary")
        self.profiles = self._db.get_container_client("userProfiles")

    async def close(self) -> None:
        await self._client.close()
        await self._credential.close()

    async def get_user_profile(self, user_id: str) -> dict | None:
        try:
            return await self.profiles.read_item(user_id, partition_key=user_id)
        except Exception:
            items = [
                i
                async for i in self.profiles.query_items(
                    query="SELECT * FROM c WHERE c.userId = @u",
                    parameters=[{"name": "@u", "value": user_id}],
                )
            ]
            return items[0] if items else None

    async def save_itinerary(self, user_id: str, items: list[dict]) -> int:
        count = 0
        for item in items:
            doc = {
                "id": str(uuid.uuid4()),
                "userId": user_id,
                "type": item.get("type", "activity"),
                "title": item.get("title", ""),
                "location": item.get("location", ""),
                "price": item.get("price", ""),
                "date": item.get("date", ""),
                "day": item.get("day", 0),
                "description": item.get("description", ""),
                "createdAt": _now(),
            }
            await self.itinerary.upsert_item(doc)
            count += 1
        return count

    async def get_itinerary(self, user_id: str) -> list[dict]:
        return [
            i
            async for i in self.itinerary.query_items(
                query="SELECT * FROM c WHERE c.userId = @u",
                parameters=[{"name": "@u", "value": user_id}],
            )
        ]

    async def clear_itinerary(self, user_id: str) -> int:
        removed = 0
        for item in await self.get_itinerary(user_id):
            await self.itinerary.delete_item(item["id"], partition_key=user_id)
            removed += 1
        return removed
