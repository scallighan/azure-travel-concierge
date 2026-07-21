# Agent Capabilities

The concierge is a single **Agent Harness** supervisor (Microsoft Agent Framework
1.12, backed by an Azure AI Foundry `gpt-5.4` deployment). It performs
**file-based skills** itself using a shared set of tools, rather than routing to
separate sub-agents.

## Supervisor (Agent Harness)

- Interprets user intent and maintains conversation memory **per named
  itinerary** — `AgentSession(session_id="{user_id}:{itinerary_id}")` backed by a
  `CosmosHistoryProvider` (`chatHistory` container).
- Advertises the file-based skills below and loads each `SKILL.md` on demand
  (progressive disclosure), then performs it with the shared tools.
- Streams responses to the UI as Server-Sent Events (`POST /invocations`).

## File-based skills (`agents/concierge_agent/skills/*/SKILL.md`)

| Skill                 | Purpose                                                          |
| --------------------- | --------------------------------------------------------------- |
| `flights`             | Search & compare flight options, schedules, fares, routes       |
| `hotel-booking`       | Find & compare hotels/lodging (with Bing Maps links)            |
| `food-entertainment`  | Restaurants, food experiences, attractions & things to do       |
| `checkout`            | Guarded purchase workflow — delegates execution to payments     |

The travel skills gather real-world information through the **Foundry Toolbox**
(`travel-concierge-toolbox`), which bundles the **WebIQ** web-intelligence tools;
when the Toolbox is not configured the harness falls back to its built-in **web
search** tool.

## Shared tools

| Tool                          | Description                                                         |
| ----------------------------- | ------------------------------------------------------------------ |
| Foundry Toolbox (MCP)         | WebIQ lookups for the travel skills + VIC payment tools (AAD-authed)|
| `payments_agent`              | **Foundry-hosted** (portal-visible) checkout agent consuming the Toolbox's VIC tools; falls back to a local Toolbox/`cart-tools` sub-agent |
| `save_itinerary`              | Persist the active itinerary's items to Cosmos DB                    |
| `search_visa_documentation`   | Retrieval-grounded visa/entry answers from **Azure AI Search**      |

Visa answers are **retrieval-grounded**: the `visa-documentation` AI Search index
is populated from `search-ingestion/visa-documentation/*.md`.

## Supporting MCP servers

`cart-tools` (cart/itinerary/checkout persistence + VIC) and `vic-mock` back the
non-LLM REST endpoints and the payments fallback path. `travel-tools` (destination
/ flight / hotel / places search) is still deployed but **superseded** by the
Toolbox's WebIQ tools for the harness skills.

| Tool (MCP `cart-tools`)               | Description                                          |
| ------------------------------------- | ---------------------------------------------------- |
| `cart_view_cart`                      | List current cart items + total                      |
| `cart_add_to_cart`                    | Add flights/hotels/activities to the cart            |
| `cart_remove_from_cart`               | Remove item(s) by identifier                         |
| `cart_clear_cart`                     | Empty the cart                                       |
| `cart_update_itinerary_date`          | Reschedule an itinerary item                          |
| `cart_check_user_has_payment_card`    | Whether a (tokenized) card is on file                |
| `cart_onboard_card`                   | Tokenize a card via mock VIC (card bypasses the LLM)|
| `cart_get_vic_iframe_config`          | Config for the (mock) hosted card-capture iframe     |
| `cart_request_purchase_confirmation`  | Step 1 — summarize order & ask user to confirm       |
| `cart_confirm_purchase`               | Step 2 — finalize and tokenize payment (mock)        |

## Mock VIC MCP server (`vic-mock`)

Stands in for the external VIC MCP server so the demo is fully self-contained.
Returns deterministic mock tokens/credentials — **no real payment processing**.

| Tool                        | Description                                       |
| --------------------------- | ------------------------------------------------- |
| `vic_secure_token`         | Issue a short-lived (mock) session token          |
| `vic_get_iframe_config`    | Hosted card-capture iframe configuration          |
| `vic_onboard_card`         | Tokenize a card → returns token + last-4 + brand  |
| `vic_initiate_purchase`    | Begin a (mock) payment authorization              |
| `vic_payment_credentials`  | Return (mock) network payment credentials         |
| `vic_health`               | Health probe                                      |

Checkout is deliberately **guarded**: the `checkout` skill only starts after the
user explicitly confirms the order, card details never enter chat, and the actual
charge is completed by the `payments_agent` tool (mock). Purchase-confirmation
notifications will be handled by WorkIQ.

## REST endpoints (non-LLM, UI support)

Card and structured-data operations bypass the model entirely:

| Endpoint                                          | Purpose                                        |
| ------------------------------------------------- | ---------------------------------------------- |
| `GET    /health`                                  | Liveness + model/vic flags                     |
| `POST   /invocations`                             | Chat (SSE streaming); body includes `itinerary_id` |
| `GET    /api/itineraries/{user_id}`               | List the user's named itineraries              |
| `POST   /api/itineraries/{user_id}`               | Create a named itinerary                        |
| `GET    /api/itinerary/{user_id}/{itinerary_id}`  | Itinerary items                                 |
| `PATCH  /api/itinerary/{user_id}/{itinerary_id}`  | Rename an itinerary                             |
| `DELETE /api/itinerary/{user_id}/{itinerary_id}`  | Delete an itinerary (+ its chat history)        |
| `GET    /api/cart/{user_id}`                      | Current cart (via `cart-tools` MCP)             |
| `GET    /api/vic/iframe-config/{user_id}`         | Mock card-capture iframe config                 |
| `POST   /api/vic/onboard-card`                    | Direct card tokenization (never sent to LLM)    |
