import os


class Config:
    PORT = int(os.getenv("PORT", "8080"))

    # Azure AI Foundry
    PROJECT_ENDPOINT = os.getenv("AZURE_AI_PROJECT_ENDPOINT", "")
    MODEL_DEPLOYMENT = os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME", "gpt-4o")

    # MCP servers
    TRAVEL_MCP_URL = os.getenv("TRAVEL_MCP_URL", "")
    CART_MCP_URL = os.getenv("CART_MCP_URL", "")

    # Cosmos DB
    COSMOS_ENDPOINT = os.getenv("COSMOS_ENDPOINT", "")
    COSMOS_DATABASE = os.getenv("COSMOS_DATABASE", "concierge")

    # Azure AI Search (Visa documentation knowledge base)
    SEARCH_ENDPOINT = os.getenv("SEARCH_ENDPOINT", "")
    SEARCH_INDEX_NAME = os.getenv("SEARCH_INDEX_NAME", "visa-documentation")

    ENABLE_VIC = os.getenv("ENABLE_VIC_INTEGRATION", "true").lower() == "true"


config = Config()
