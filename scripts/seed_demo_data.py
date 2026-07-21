"""
Seed a demo user profile into Cosmos DB so the concierge has profile context.

Usage:
    export COSMOS_ENDPOINT="https://<acct>.documents.azure.com:443/"
    export COSMOS_DATABASE="concierge"
    export DEMO_USER_ID="demo-user"
    export DEMO_EMAIL="you@example.com"
    python seed_demo_data.py
"""

import os
from datetime import datetime, timezone

from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential

endpoint = os.environ["COSMOS_ENDPOINT"]
database = os.getenv("COSMOS_DATABASE", "concierge")
user_id = os.getenv("DEMO_USER_ID", "demo-user")
email = os.getenv("DEMO_EMAIL", "traveler@example.com")

client = CosmosClient(endpoint, credential=DefaultAzureCredential())
profiles = client.get_database_client(database).get_container_client("userProfiles")

profiles.upsert_item({
    "id": user_id,
    "userId": user_id,
    "name": "Demo Traveler",
    "email": email,
    "address": "1 Market St, Seattle, WA",
    "preferences": {"seat": "aisle", "hotel": "boutique", "cuisine": "local"},
    "onboardingCompleted": True,
    "updatedAt": datetime.now(timezone.utc).isoformat(),
})
print(f"Seeded profile for {user_id}.")
