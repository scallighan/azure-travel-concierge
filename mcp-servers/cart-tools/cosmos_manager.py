"""
Cosmos DB data access for cart, itinerary, user profiles and orders.

Uses Entra ID (DefaultAzureCredential) for the data plane — no account keys.
Containers are all partitioned by ``/userId``.
"""

import logging
import os
import uuid
from datetime import datetime, timezone

from azure.cosmos import CosmosClient, PartitionKey
from azure.identity import DefaultAzureCredential

logger = logging.getLogger("cart-cosmos")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CosmosManager:
    def __init__(self) -> None:
        endpoint = os.environ["COSMOS_ENDPOINT"]
        database = os.getenv("COSMOS_DATABASE", "concierge")
        credential = DefaultAzureCredential()
        self._client = CosmosClient(endpoint, credential=credential)
        self._db = self._client.get_database_client(database)
        self.cart = self._db.get_container_client("cart")
        self.itinerary = self._db.get_container_client("itinerary")
        self.profiles = self._db.get_container_client("userProfiles")
        self.orders = self._db.get_container_client("orders")
        logger.info("CosmosManager ready (db=%s)", database)

    # ------------------------------------------------------------------ cart
    def get_cart(self, user_id: str) -> list[dict]:
        return list(
            self.cart.query_items(
                query="SELECT * FROM c WHERE c.userId = @u",
                parameters=[{"name": "@u", "value": user_id}],
                partition_key=user_id,
            )
        )

    def add_cart_item(self, user_id: str, item: dict) -> dict:
        doc = {
            "id": str(uuid.uuid4()),
            "userId": user_id,
            "item_type": item.get("item_type", "product"),
            "title": item["title"],
            "price": item.get("price", ""),
            "asin": item.get("asin", ""),
            "url": item.get("url", ""),
            "createdAt": _now(),
            "updatedAt": _now(),
        }
        if doc["item_type"] == "hotel":
            doc.update({
                "hotel_id": item.get("hotel_id", ""),
                "city_code": item.get("city_code", ""),
                "rating": item.get("rating", ""),
                "amenities": item.get("amenities", ""),
                "check_in_date": item.get("check_in_date", ""),
            })
        elif doc["item_type"] == "flight":
            doc.update({
                "flight_id": item.get("flight_id", ""),
                "origin": item.get("origin", ""),
                "destination": item.get("destination", ""),
                "departure_date": item.get("departure_date", ""),
                "airline": item.get("airline", ""),
            })
        self.cart.upsert_item(doc)
        return doc

    def remove_cart_items(self, user_id: str, identifiers: list[str], item_type: str) -> int:
        id_field = {"product": "asin", "hotel": "hotel_id", "flight": "flight_id"}.get(item_type, "asin")
        removed = 0
        for item in self.get_cart(user_id):
            if item.get("item_type") == item_type and item.get(id_field) in identifiers:
                self.cart.delete_item(item["id"], partition_key=user_id)
                removed += 1
        return removed

    def clear_cart(self, user_id: str) -> int:
        removed = 0
        for item in self.get_cart(user_id):
            self.cart.delete_item(item["id"], partition_key=user_id)
            removed += 1
        return removed

    def update_item_date(self, user_id: str, identifier: str, item_type: str, new_date: str) -> int:
        id_field = "flight_id" if item_type == "flight" else "hotel_id"
        date_field = "departure_date" if item_type == "flight" else "check_in_date"
        updated = 0
        for item in self.get_cart(user_id):
            if item.get("item_type") == item_type and item.get(id_field) == identifier:
                item[date_field] = new_date
                item["updatedAt"] = _now()
                self.cart.upsert_item(item)
                updated += 1
        return updated

    # -------------------------------------------------------------- profiles
    def get_user_profile(self, user_id: str) -> dict | None:
        try:
            return self.profiles.read_item(user_id, partition_key=user_id)
        except Exception:
            items = list(
                self.profiles.query_items(
                    query="SELECT * FROM c WHERE c.userId = @u",
                    parameters=[{"name": "@u", "value": user_id}],
                    partition_key=user_id,
                )
            )
            return items[0] if items else None

    def set_payment_card(self, user_id: str, card: dict) -> dict:
        profile = self.get_user_profile(user_id) or {"id": user_id, "userId": user_id}
        profile["paymentCard"] = card
        profile["updatedAt"] = _now()
        self.profiles.upsert_item(profile)
        return profile

    # ---------------------------------------------------------------- orders
    def create_order(self, user_id: str, order: dict) -> dict:
        doc = {"id": order.get("order_id", str(uuid.uuid4())), "userId": user_id, "createdAt": _now(), **order}
        self.orders.upsert_item(doc)
        return doc
