"""
Cosmos DB access for the concierge: named multi-itinerary management + user
profiles. Entra ID data-plane auth (async DefaultAzureCredential).

Each itinerary is stored as a single document in the ``itinerary`` container:

    {
        "id": "<itineraryId>",          # partitioned by userId
        "userId": "<userId>",
        "kind": "itinerary",
        "name": "Tokyo Spring 2026",
        "items": [ {type,title,location,price,date,day,description}, ... ],
        "createdAt": "...", "updatedAt": "..."
    }
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


def _summary(doc: dict) -> dict:
    """Lightweight itinerary descriptor for list views."""
    return {
        "id": doc["id"],
        "name": doc.get("name", "Untitled itinerary"),
        "itemCount": len(doc.get("items", [])),
        "createdAt": doc.get("createdAt"),
        "updatedAt": doc.get("updatedAt"),
    }


class CosmosManager:
    def __init__(self) -> None:
        self._credential = DefaultAzureCredential()
        self._client = CosmosClient(config.COSMOS_ENDPOINT, credential=self._credential)
        self._db = self._client.get_database_client(config.COSMOS_DATABASE)
        self.itinerary = self._db.get_container_client(config.COSMOS_ITINERARY_CONTAINER)
        self.profiles = self._db.get_container_client("userProfiles")

    async def close(self) -> None:
        await self._client.close()
        await self._credential.close()

    # --- user profile -------------------------------------------------------
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

    # --- itinerary CRUD -----------------------------------------------------
    async def list_itineraries(self, user_id: str) -> list[dict]:
        docs = [
            i
            async for i in self.itinerary.query_items(
                query="SELECT * FROM c WHERE c.userId = @u AND c.kind = 'itinerary'",
                parameters=[{"name": "@u", "value": user_id}],
            )
        ]
        docs.sort(key=lambda d: d.get("createdAt", ""))
        return [_summary(d) for d in docs]

    async def create_itinerary(self, user_id: str, name: str) -> dict:
        doc = {
            "id": str(uuid.uuid4()),
            "userId": user_id,
            "kind": "itinerary",
            "name": name or "Untitled itinerary",
            "items": [],
            "createdAt": _now(),
            "updatedAt": _now(),
        }
        await self.itinerary.upsert_item(doc)
        return _summary(doc)

    async def get_itinerary(self, user_id: str, itinerary_id: str) -> dict | None:
        try:
            doc = await self.itinerary.read_item(itinerary_id, partition_key=user_id)
        except Exception:
            return None
        if doc.get("kind") != "itinerary" or doc.get("userId") != user_id:
            return None
        return doc

    async def rename_itinerary(self, user_id: str, itinerary_id: str, name: str) -> bool:
        doc = await self.get_itinerary(user_id, itinerary_id)
        if not doc:
            return False
        doc["name"] = name
        doc["updatedAt"] = _now()
        await self.itinerary.upsert_item(doc)
        return True

    async def delete_itinerary(self, user_id: str, itinerary_id: str) -> bool:
        if not await self.get_itinerary(user_id, itinerary_id):
            return False
        await self.itinerary.delete_item(itinerary_id, partition_key=user_id)
        return True

    async def save_items(self, user_id: str, itinerary_id: str, items: list[dict]) -> int:
        """Replace the items of an itinerary with a normalized list."""
        doc = await self.get_itinerary(user_id, itinerary_id)
        if not doc:
            # Auto-create so the agent never loses a plan if the id drifted.
            doc = {
                "id": itinerary_id,
                "userId": user_id,
                "kind": "itinerary",
                "name": "Untitled itinerary",
                "createdAt": _now(),
            }
        doc["items"] = [
            {
                "type": it.get("type", "activity"),
                "title": it.get("title", ""),
                "location": it.get("location", ""),
                "price": it.get("price", ""),
                "date": it.get("date", ""),
                "day": it.get("day", 0),
                "description": it.get("description", ""),
            }
            for it in items
        ]
        doc["updatedAt"] = _now()
        await self.itinerary.upsert_item(doc)
        return len(doc["items"])

    async def get_items(self, user_id: str, itinerary_id: str) -> list[dict]:
        doc = await self.get_itinerary(user_id, itinerary_id)
        return doc.get("items", []) if doc else []
