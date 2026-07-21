# Architecture

An Azure-native re-implementation of the AWS Bedrock AgentCore
[travel-concierge-agent](https://github.com/aurbac/amazon-bedrock-agentcore-samples/tree/main/05-blueprints/travel-concierge-agent)
blueprint, built on **Azure AI Foundry** and the **Microsoft Agent Framework**.

## High-level diagram

```
                          ┌───────────────────────────┐
                          │   Azure Static Web App     │
                          │   (React + Vite SPA)       │
                          │   MSAL / Entra sign-in     │
                          └─────────────┬─────────────┘
                                        │ HTTPS (SSE stream + REST)
                                        ▼
                     ┌──────────────────────────────────────┐
                     │   Concierge Agent (Container App)     │
                     │   FastAPI  /invocations (SSE)         │
                     │           /api/cart /api/itinerary    │
                     │           /api/vic/*                 │
                     │                                       │
                     │   Microsoft Agent Framework           │
                     │   Supervisor Agent (FoundryChatClient)│
                     │    ├─ travel_assistant (sub-agent)    │
                     │    └─ cart_manager     (sub-agent)    │
                     └───┬─────────────┬──────────────┬──────┘
                         │ MCP         │ MCP          │ direct SDK
              ┌──────────▼───┐ ┌───────▼────────┐ ┌───▼──────────┐
              │ travel-tools │ │  cart-tools    │ │ Azure AI     │
              │ MCP (ACA)    │ │  MCP (ACA)     │ │ Search       │
              │ internal     │ │  internal      │ │ (visa docs)  │
              └──────────────┘ └───┬────────────┘ └──────────────┘
                                   │ MCP           ┌──────────────┐
                            ┌──────▼───────┐       │ Cosmos DB    │
                            │ vic-mock    │       │ (NoSQL)      │
                            │ MCP (ACA)    │       │ cart/itin/   │
                            │ internal     │       │ profile/order│
                            └──────────────┘       └──────────────┘

  Foundry (gpt-4o + text-embedding) · Key Vault · Log Analytics / App Insights
  All service-to-service auth via a User-Assigned Managed Identity (Entra RBAC).
```

## Component mapping (AWS → Azure)

| AWS Bedrock sample                     | This Azure implementation                              |
| -------------------------------------- | ------------------------------------------------------ |
| Bedrock AgentCore Runtime + Gateway    | Azure AI Foundry + Azure Container Apps                 |
| Strands Agents SDK                     | Microsoft Agent Framework (`agent-framework-foundry`)  |
| Bedrock foundation model (Claude/Nova) | Foundry model deployment (`gpt-4o`)                     |
| Amazon DynamoDB                        | Azure Cosmos DB for NoSQL (serverless)                 |
| Amazon Cognito                         | Microsoft Entra ID (SPA app registration)              |
| AWS Amplify Hosting                    | Azure Static Web Apps                                   |
| Bedrock Knowledge Base (visa docs)     | Azure AI Search (`visa-documentation` index)           |
| Amazon SES                             | _Removed_ — notifications to be handled by WorkIQ      |
| AWS Secrets Manager                    | Azure Key Vault                                         |
| VIC MCP server (external)              | **Mock VIC MCP server** (`mcp-servers/vic-mock`)     |
| IAM roles                              | User-Assigned Managed Identity + Entra RBAC            |

## Agents & tools

The **supervisor** agent orchestrates two sub-agents (exposed to the supervisor
as callable tools via `agent.as_tool(...)`):

- **travel_assistant** — destination research, flights, hotels, activities, and
  **visa requirements** (grounded on Azure AI Search). Backed by the
  `travel-tools` MCP server + a `search_visa_docs` function tool.
- **cart_manager** — cart management, itinerary building, and the two-step
  purchase/checkout flow. Backed by the `cart-tools` MCP server, which persists
  to Cosmos DB and calls the mock VIC server for payment tokenization.

MCP servers are reached over **Streamable HTTP** at `/mcp`. In Azure they run as
internal-ingress Container Apps; the agent builds their internal FQDNs from
Terraform-provided environment variables.

## Data model (Cosmos DB, partition key `/userId`)

| Container      | Purpose                                        |
| -------------- | ---------------------------------------------- |
| `userProfiles` | Traveler profile & preferences                 |
| `cart`         | Active shopping cart items                      |
| `itinerary`    | Planned trip items (day-by-day)                |
| `orders`       | Completed purchases / booking confirmations    |

## Payment data flow (card never touches the LLM)

Mirroring the AWS sample's local-vic-server REST design, sensitive card data is
kept **out of the model's context**:

1. The React UI collects card details in `VicCardModal` and `POST`s them to the
   agent's REST endpoint `POST /api/vic/onboard-card`.
2. The agent forwards them via a **direct MCP call** (`mcp_direct.call_mcp_tool`)
   to `cart-tools` → `vic-mock`, which returns a **token** (mock) and last-4.
3. Only the token/last-4 is persisted; the LLM only ever sees "a card ending
   in 1111 is on file."

## Security

- **No keys**: Cosmos `local_authentication_disabled`, Foundry `disableLocalAuth`,
  and Search `local_authentication_enabled=false`. All access uses the
  User-Assigned Managed Identity with data-plane RBAC role assignments.
- SPA users sign in with Entra ID (MSAL); mock-auth mode is available for demos.
- Observability via Log Analytics + Application Insights.

See [DEPLOYMENT.md](DEPLOYMENT.md) to provision and run, and
[AGENT_CAPABILITIES.md](AGENT_CAPABILITIES.md) for the full tool catalog.
