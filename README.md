# Azure Travel Concierge Agent

An **Azure AI Foundry** re-implementation of the AWS Bedrock AgentCore
[travel-concierge-agent](https://github.com/aurbac/amazon-bedrock-agentcore-samples/tree/main/05-blueprints/travel-concierge-agent)
blueprint, built entirely with Microsoft & Azure products:

- **Microsoft Agent Framework** for the multi-agent supervisor/sub-agent pattern
- **Azure AI Foundry** (`gpt-4o` + embeddings) as the model backbone
- **Azure AI Search** for retrieval-grounded visa guidance
- **Azure Cosmos DB for NoSQL** for cart / itinerary / profile / orders
- **Azure Container Apps** for the agent and MCP tool servers
- **Azure Static Web Apps** + **Entra ID** for the React chat UI
- **Terraform** (azurerm + azapi + azuread) for all infrastructure
- A self-contained **mock VIC MCP server** (no external VIC access required)

## Repository layout

```
agents/concierge_agent/   Supervisor agent (FastAPI + Microsoft Agent Framework)
mcp-servers/
  travel-tools/           MCP: destination / flight / hotel search
  cart-tools/             MCP: cart, itinerary, checkout (Cosmos + VIC)
  vic-mock/              MCP: mock VIC tokenization / payment
search-ingestion/         Push visa docs into Azure AI Search
web-ui/                   React + Vite SPA (chat, cart, itinerary, card modal)
terraform/                All Azure infrastructure as code
scripts/                  build-images.sh, deploy.sh, deploy-webui.sh, seed_demo_data.py
docs/                     ARCHITECTURE / DEPLOYMENT / AGENT_CAPABILITIES
```

## Quick start

```bash
export GH_REPO="your-org/travel-concierge-azure"
az login
./scripts/deploy.sh          # build images -> terraform apply -> seed -> ingest -> deploy UI
```

`deploy.sh` also builds and publishes the React UI to the Static Web App. To
(re)deploy just the UI later, run `./scripts/deploy-webui.sh` (see
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md#4-build--deploy-the-web-ui)).

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — components, AWS→Azure mapping, data & payment flows
- [Deployment](docs/DEPLOYMENT.md) — prerequisites and step-by-step provisioning
- [Agent Capabilities](docs/AGENT_CAPABILITIES.md) — full agent + MCP tool catalog

## Design highlights

- **Keyless by default** — Cosmos, Foundry, and AI Search have local auth
  disabled; all access flows through a User-Assigned Managed Identity with Entra
  RBAC role assignments.
- **Card data never reaches the LLM** — card capture is a direct REST → MCP path
  to the (mock) tokenization service; the model only ever sees a token / last-4.
- **Fully mockable demo** — the mock VIC MCP server and deterministic travel
  data make the whole experience runnable without any third-party credentials.

> **Note:** the VIC integration here is a **mock** for demonstration only and
> performs no real payment processing.
