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
                     │           /api/itineraries /itinerary │
                     │           /api/cart /api/vic/*        │
                     │                                       │
                     │   Microsoft Agent Framework 1.12      │
                     │   Agent Harness (FoundryChatClient)   │
                     │    ├─ file-based skills (SKILL.md):   │
                     │    │   flights · hotel-booking ·      │
                     │    │   food-entertainment · checkout  │
                     │    ├─ save_itinerary (fn tool)        │
                     │    ├─ search_visa_documentation (fn)  │
                     │    └─ payments_agent (Foundry-hosted) │
                     └──┬────────────┬───────────┬──────────┘
                        │ MCP        │ direct SDK │ MCP (Toolbox, AAD)
              ┌─────────▼────┐ ┌─────▼──────┐ ┌──▼───────────────────┐
              │ cart-tools   │ │ Azure AI   │ │ Foundry Toolbox      │
              │ MCP (ACA)    │ │ Search     │ │ travel-concierge-... │
              │ internal     │ │ (visa docs)│ │  WebIQ + VIC tools   │
              └────┬─────────┘ └────────────┘ └──────────────────────┘
                   │ MCP           ┌──────────────┐
            ┌──────▼───────┐       │ Cosmos DB    │  named multi-itineraries
            │ vic-mock     │       │ (NoSQL)      │  + per-itinerary chat
            │ MCP (ACA)    │       │ profile/cart/│    history
            │ internal     │       │ itin/orders/ │
            └──────────────┘       │ chatHistory  │
                                   └──────────────┘

  Foundry (gpt-5.4 + text-embedding) · Cosmos · Storage · Key Vault (all
  private-endpoint only) · Log Analytics / App Insights.
  All service-to-service auth via a User-Assigned Managed Identity (Entra RBAC).
  travel-tools MCP is still deployed but superseded by the Toolbox's WebIQ tools.
```

## Component mapping (AWS → Azure)

| AWS Bedrock sample                     | This Azure implementation                              |
| -------------------------------------- | ------------------------------------------------------ |
| Bedrock AgentCore Runtime + Gateway    | Azure AI Foundry + Azure Container Apps                 |
| Strands Agents SDK                     | Microsoft Agent Framework 1.12 **Agent Harness**       |
| Bedrock foundation model (Claude/Nova) | Foundry model deployment (`gpt-5.4`)                   |
| Amazon DynamoDB                        | Azure Cosmos DB for NoSQL (serverless)                 |
| Amazon Cognito                         | Microsoft Entra ID (SPA app registration)              |
| AWS Amplify Hosting                    | Azure Static Web Apps                                   |
| Bedrock Knowledge Base (visa docs)     | Azure AI Search (`visa-documentation` index)           |
| Amazon SES                             | _Removed_ — notifications to be handled by WorkIQ      |
| AWS Secrets Manager                    | Azure Key Vault                                         |
| VIC MCP server (external)              | **Mock VIC MCP server** (`mcp-servers/vic-mock`), also surfaced via the Foundry Toolbox |
| IAM roles                              | User-Assigned Managed Identity + Entra RBAC            |

## Agents, skills & tools

The concierge is a single **Agent Harness** supervisor (`create_harness_agent`,
`FoundryChatClient`). It performs **file-based skills** itself — progressive
`SKILL.md` files under `agents/concierge_agent/skills/`, advertised in the system
prompt and loaded on demand — using a shared set of tools:

- **flights**, **hotel-booking**, **food-entertainment** — look up real-world
  travel information using the **Foundry Toolbox** (`travel-concierge-toolbox`,
  which bundles the **WebIQ** web-intelligence tools). When the Toolbox is not
  configured, the harness falls back to its built-in **web search** tool.
- **checkout** — the guarded purchase workflow; execution is delegated to the
  `payments_agent` tool.

Shared tools passed to the harness:

- **Foundry Toolbox MCP tool** — connected once at startup over Streamable HTTP
  with an AAD bearer token (`https://ai.azure.com/.default`); serves WebIQ (for
  the travel skills) and the VIC payment tools.
- **`payments_agent`** — a **Foundry-hosted, portal-visible** agent (registered
  via `AIProjectClient.agents.create_version`) that consumes the Toolbox's VIC
  tools and is invoked through the `agent_reference` responses API. If the
  Toolbox/project is unavailable it degrades to a local sub-agent backed by the
  Toolbox or the `cart-tools` MCP.
- **`save_itinerary`** — persists the active itinerary's items to Cosmos.
- **`search_visa_documentation`** — retrieval-grounded visa/entry answers from
  Azure AI Search.

Conversation memory is a `CosmosHistoryProvider` scoped per itinerary via
`AgentSession(session_id=f"{user_id}:{itinerary_id}")`, so each **named
itinerary** has its own independent chat thread.

MCP servers are reached over **Streamable HTTP** at `/mcp`. In Azure they run as
internal-ingress Container Apps; the agent builds their internal FQDNs from
Terraform-provided environment variables. `cart-tools` / `vic-mock` back the
non-LLM REST endpoints (and the payments fallback); the Foundry Toolbox is the
primary path for travel lookups and payments.

## Data model (Cosmos DB, database `concierge`)

| Container      | Partition     | Purpose                                        |
| -------------- | ------------- | ---------------------------------------------- |
| `userProfiles` | `/userId`     | Traveler profile & preferences                 |
| `cart`         | `/userId`     | Active shopping cart items                      |
| `itinerary`    | `/userId`     | Named itineraries — one document per itinerary (items day-by-day) |
| `orders`       | `/userId`     | Completed purchases / booking confirmations    |
| `chatHistory`  | `/session_id` | Per-itinerary chat memory (`CosmosHistoryProvider`) |

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
  Search `local_authentication_enabled=false`, and Storage
  `shared_access_key_enabled=false`. All access uses the User-Assigned Managed
  Identity with data-plane RBAC role assignments.
- **Private networking**: Cosmos DB, Storage and Key Vault have public network
  access disabled and are reached over **private endpoints** from the
  VNet-injected Container Apps environment (private DNS zones link the VNet).
  Azure AI Search reaches Storage via a **shared private link** (its private
  endpoint connection is approved once before ingestion).
- **Card data never reaches the LLM** — see the payment data flow above.
- SPA users sign in with Entra ID (MSAL); mock-auth mode is available for demos.
- Observability via Log Analytics + Application Insights.

See [DEPLOYMENT.md](DEPLOYMENT.md) to provision and run, and
[AGENT_CAPABILITIES.md](AGENT_CAPABILITIES.md) for the full tool catalog.
