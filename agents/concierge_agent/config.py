import os


class Config:
    PORT = int(os.getenv("PORT", "8080"))

    # Azure AI Foundry
    PROJECT_ENDPOINT = os.getenv("AZURE_AI_PROJECT_ENDPOINT", "")
    MODEL_DEPLOYMENT = os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME", "gpt-4o")

    # MCP servers (internal Container Apps FQDNs). CART_MCP_URL still backs the
    # direct REST->MCP cart/card endpoints in app.py (and the local payments
    # fallback when no Foundry Toolbox is configured).
    TRAVEL_MCP_URL = os.getenv("TRAVEL_MCP_URL", "")
    CART_MCP_URL = os.getenv("CART_MCP_URL", "")

    # Foundry Toolbox (travel-concierge-toolbox) exposes WebIQ (web intelligence)
    # and the VIC payment tools through one MCP-compatible endpoint. The skills
    # and the payments agent consume it; auth is centralized (AAD bearer).
    FOUNDRY_TOOLBOX_NAME = os.getenv("FOUNDRY_TOOLBOX_NAME", "travel-concierge-toolbox")
    # Optional pin; when blank the default version is resolved at startup.
    FOUNDRY_TOOLBOX_VERSION = os.getenv("FOUNDRY_TOOLBOX_VERSION", "")

    # Foundry-hosted Payments agent (visible in the Foundry portal).
    PAYMENTS_AGENT_NAME = os.getenv("PAYMENTS_AGENT_NAME", "travel-payments-agent")
    # The Foundry project connection (RemoteTool/MCP) for the mock VIC payment
    # service. The payments agent talks to this directly rather than through the
    # shared Toolbox, so all payment traffic flows through the mock VIC server.
    VIC_MCP_CONNECTION = os.getenv("VIC_MCP_CONNECTION", "vic-mock")
    # Optional explicit override for the mock VIC MCP URL; when blank it is
    # resolved from the connection's target at startup.
    VIC_MCP_URL = os.getenv("VIC_MCP_URL", "")

    # Cosmos DB
    COSMOS_ENDPOINT = os.getenv("COSMOS_ENDPOINT", "")
    COSMOS_DATABASE = os.getenv("COSMOS_DATABASE", "concierge")
    # Container holding one document per named itinerary (partition /userId).
    COSMOS_ITINERARY_CONTAINER = os.getenv("COSMOS_ITINERARY_CONTAINER", "itinerary")
    # Container backing the MAF CosmosHistoryProvider (partition /session_id).
    COSMOS_HISTORY_CONTAINER = os.getenv("COSMOS_HISTORY_CONTAINER", "chatHistory")

    ENABLE_VIC = os.getenv("ENABLE_VIC_INTEGRATION", "true").lower() == "true"

    @property
    def toolbox_configured(self) -> bool:
        return bool(self.PROJECT_ENDPOINT and self.FOUNDRY_TOOLBOX_NAME)


config = Config()
