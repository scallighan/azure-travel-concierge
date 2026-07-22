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
                                        │ HTTPS (AG-UI protocol + REST)
                                        ▼
                     ┌──────────────────────────────────────┐
                     │   Concierge Agent (Container App)     │
                     │   FastAPI  /agui (AG-UI, SSE)         │
                     │           /api/itineraries /itinerary │
                     │           /api/orders /api/vic/*      │
                     │                                       │
                     │   Microsoft Agent Framework 1.12      │
                     │   Agent Harness (FoundryChatClient)   │
                     │    ├─ file-based skills (SKILL.md):   │
                     │    │   flights · hotel-booking ·      │
                     │    │   food-entertainment · maps ·    │
                     │    │   weather · checkout              │
                     │    ├─ save_itinerary (fn tool)        │
                     │    └─ payments_agent (Foundry-hosted) │
                     └──┬────────────────────────┬──────────┘
                        │ MCP                     │ MCP (Toolbox, AAD)
              ┌─────────▼────┐          ┌─────────▼────────────┐
              │ cart-tools   │          │ Foundry Toolbox      │
              │ MCP (ACA)    │          │ travel-concierge-... │
              │ internal     │          │  WebIQ + VIC tools   │
              └────┬─────────┘          └──────────────────────┘
                   │ MCP           ┌──────────────┐
            ┌──────▼───────┐       │ Cosmos DB    │  named multi-itineraries
            │ cart-tools   │       │ (NoSQL)      │  + per-itinerary chat
            │ orchestrates │       │ profile/cart/│    history
            │ VIC + merchant│      │ itin/orders/ │
            └──┬────────┬──┘       │ chatHistory  │
               │ MCP    │ MCP      └──────────────┘
        ┌──────▼────┐ ┌─▼────────────┐
        │ vic-mock  │ │ merchant-mock│  settles VIC network-token
        │ MCP (ACA) │ │ MCP (ACA)    │  credentials → creates order
        │ (Visa/VDP)│ │ (acquirer)   │
        └───────────┘ └──────────────┘

  Foundry (gpt-5.4 + text-embedding) · Cosmos · Storage · Key Vault (all
  private-endpoint only) · Log Analytics / App Insights. Azure AI Search
  (visa-documentation index) is provisioned and fed by the search-ingestion
  pipeline, but is not queried by the agent at runtime.
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
| VIC MCP server (external)              | **Mock VIC (Visa) MCP server** (`mcp-servers/vic-mock`) + **mock merchant/acquirer** (`mcp-servers/merchant-mock`) — the two separate agentic-commerce parties |
| IAM roles                              | User-Assigned Managed Identity + Entra RBAC            |

## Agents, skills & tools

The concierge is a single **Agent Harness** supervisor (`create_harness_agent`,
`FoundryChatClient`). It performs **file-based skills** itself — progressive
`SKILL.md` files under `agents/concierge_agent/skills/`, advertised in the system
prompt and loaded on demand — using a shared set of tools:

- **flights**, **hotel-booking**, **food-entertainment**, **maps**, **weather** —
  look up real-world travel information using the **Foundry Toolbox**
  (`travel-concierge-toolbox`, which bundles the **WebIQ** web-intelligence tools).
  When the Toolbox is not configured, the harness falls back to its built-in **web
  search** tool. The **maps** skill is read-only: it resolves a place's exact
  name/address and a Bing Maps link and answers proximity questions (e.g.
  "restaurants near my hotel") using WebIQ `places`. The **weather** skill is also
  read-only: it reads the destination and dates already on the active itinerary and
  returns a day-by-day forecast table (WebIQ `web`/`browse`). The **flights** skill
  attaches a real **booking link** to every option and carries it onto the saved
  `flight` item as `booking_url` (surfaced in the itinerary UI).
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

Conversation memory is a `CosmosHistoryProvider` scoped per itinerary via
`AgentSession(session_id=f"{user_id}:{itinerary_id}")`, so each **named
itinerary** has its own independent chat thread. Because the transcript lives in
Cosmos, the UI restores it from `GET /api/history/{user_id}/{itinerary_id}` when
the user switches itineraries or reloads — the visible conversation follows the
active itinerary.

## Chat transport (AG-UI protocol)

The SPA talks to the agent over the **AG-UI protocol**. The server exposes a
single `POST /agui` endpoint via
`agent_framework.ag_ui.add_agent_framework_fastapi_endpoint`, which streams
AG-UI events (`RUN_STARTED` → `TEXT_MESSAGE_*` → `RUN_FINISHED`) over SSE. The
web-ui parses that SSE stream directly with a small custom reader (see
`web-ui/src/lib/agentClient.ts`) rather than `@ag-ui/client`'s `HttpAgent`: the
harness resume stream is not self-contained (on resume it emits
`TOOL_CALL_END`/`TOOL_CALL_RESULT` for tool calls whose `TOOL_CALL_START` was in
the prior interrupted run), which the library's strict per-run event verifier
rejects.

Human-in-the-loop tool approvals are surfaced as AG-UI interrupts:
`add_agent_framework_fastapi_endpoint` (via `require_confirmation`, default on)
finishes a run with `RUN_FINISHED outcome={type:"interrupt", ...}` when the
harness hits an `approval_mode="always_require"` tool (e.g. `load_skill`,
checkout). The UI renders an Approve/Reject prompt and resumes by re-POSTing to
`/agui` with `resume=[{interruptId, status:"resolved", payload:{accepted}}]`.
Resolving one approval can surface the next, so the client loops until the run
finishes with no interrupts. The pending-approval state is held **in-process**
(keyed by `thread_id`), so the agent runs as a **single replica**.

Because the concierge builds a fresh harness supervisor per turn (to inject the
user profile + active itinerary into the instructions), a thin
`AGUISupervisor` adapter (`SupportsAgentRun`) resolves the active
`(user_id, itinerary_id)` from each run's `forwardedProps` (the AG-UI
`thread_id` is `"user_id:itinerary_id"`) and delegates to the shared harness.
The client sends only the new user message each turn — Cosmos
(`CosmosHistoryProvider`, keyed by `thread_id`) remains the single source of
truth for history, so the transcript is never resent.

MCP servers are reached over **Streamable HTTP** at `/mcp`. In Azure they run as
internal-ingress Container Apps; the agent builds their internal FQDNs from
Terraform-provided environment variables. `cart-tools` orchestrates the non-LLM
REST endpoints and the checkout flow, calling `vic-mock` (Visa: tokens, mandates,
credentials) and `merchant-mock` (acquirer: settlement + order) as the two
separate agentic-commerce parties.

## Data model (Cosmos DB, database `concierge`)

| Container      | Partition     | Purpose                                        |
| -------------- | ------------- | ---------------------------------------------- |
| `userProfiles` | `/userId`     | Traveler profile & preferences                 |
| `cart`         | `/userId`     | Legacy cart container (retained for the local checkout fallback; the primary flow uses `itinerary` + `orders`, not a shopping cart) |
| `itinerary`    | `/userId`     | Named itineraries — one document per itinerary (items day-by-day) |
| `orders`       | `/userId`     | Completed purchases / booking confirmations. Written on successful checkout — by `cart-tools` (fallback path) or by the concierge after the Foundry payments agent succeeds (snapshots the itinerary items + VIC transaction ref). Surfaced in the UI "Past Orders" panel via `GET /api/orders/{user_id}` |
| `chatHistory`  | `/session_id` | Per-itinerary chat memory (`CosmosHistoryProvider`) |
| `vicCards`     | `/userId`     | Durable mock-card store for vic-mock (token + card metadata, never a PAN) so enrolled cards survive a restart |

## Payment data flow (card never touches the LLM)

Sensitive card data is kept **out of the model's context**, and the payment path
mirrors the real Visa Intelligent Commerce (VIC) agentic-commerce flow:

1. The React UI collects card details in `VicCardModal` and `POST`s them to the
   agent's REST endpoint `POST /api/vic/onboard-card`.
2. The agent forwards them via a **direct MCP call** (`mcp_direct.call_mcp_tool`)
   to `cart-tools` → `vic-mock`, which enrolls the PAN with VTS
   (`vic_enroll_pan`), provisions a **network token** (`vic_provision_token`),
   and enrolls it for agentic commerce (`vic_enroll_card`). Only the token and
   last-4 are returned.
3. **VIC is the source of truth for the card.** Cosmos stores only a *pointer* —
   the `vProvisionedTokenId` — not the card details. `vic-mock` indexes the card
   by `user_id` (relationship built at `vic_enroll_card`); `cart_check_user_has_payment_card`
   resolves the card by calling `vic_get_card(user_id)`, so the UI's "card on
   file" state always reflects what VIC actually holds. The LLM only ever sees
   "a card ending in 1111 is on file."
4. At checkout, `cart-tools` runs the agentic-commerce flow across the two
   separate parties, mirroring VIC:
   - **Visa (`vic-mock`)** — create an **instruction + spending mandate** scoped
     to the confirmed total (`vic_create_instruction`), then retrieve
     per-transaction network-token **credentials**, which are **declined if they
     exceed the mandate** (`vic_retrieve_credentials`).
   - **Merchant (`merchant-mock`)** — the agent **presents those credentials** to
     the merchant/acquirer (`merchant_authorize`), which validates the DPAN +
     cryptogram, authorizes/settles, and creates the merchant order. The merchant
     never sees the PAN.
   - **Visa (`vic-mock`)** — confirm the outcome back to Visa
     (`vic_confirm_transaction`) so the mandate ledger reflects the final state.
   The mocks keep the real Visa field names and call ordering but perform no real
   cryptography or settlement.

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
- **Observability**: Log Analytics + Application Insights. Application Insights is
  connected to the Foundry account/project (`AppInsights` connection), so agent
  runs and GenAI traces surface in the Foundry portal's tracing view.

See [DEPLOYMENT.md](DEPLOYMENT.md) to provision and run, and
[AGENT_CAPABILITIES.md](AGENT_CAPABILITIES.md) for the full tool catalog.
