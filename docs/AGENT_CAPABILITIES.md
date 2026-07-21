# Agent Capabilities

The concierge is a **supervisor** agent (Microsoft Agent Framework, backed by an
Azure AI Foundry `gpt-4o` deployment) that routes each request to one of two
sub-agents. Sub-agents are exposed to the supervisor as callable tools; each
sub-agent in turn calls MCP tools and Azure services.

## Supervisor

- Interprets user intent, maintains conversation memory per `user_id:session_id`
  (`AgentSession`), and delegates to sub-agents.
- Streams responses to the UI as Server-Sent Events (`POST /invocations`).

## travel_assistant sub-agent

Destination research, trip planning, and visa guidance.

| Tool (MCP `travel-tools`)             | Description                                       |
| ------------------------------------- | ------------------------------------------------- |
| `travel_search`                       | General destination / things-to-do research      |
| `travel_places_search`                | Points of interest & attractions                  |
| `travel_hotel_search`                 | Hotel availability by dates                        |
| `travel_flight_search`                | Flight options between cities/dates                |
| `search_visa_docs` (function tool)    | Grounded visa requirements from **Azure AI Search** |

Visa answers are **retrieval-grounded**: the `visa-documentation` AI Search index
is populated from `search-ingestion/visa-documentation/*.md`.

## cart_manager sub-agent

Cart, itinerary, and the two-step checkout flow (persisted to Cosmos DB).

| Tool (MCP `cart-tools`)               | Description                                          |
| ------------------------------------- | ---------------------------------------------------- |
| `cart_view_cart`                      | List current cart items + total                      |
| `cart_add_to_cart`                    | Add flights/hotels/activities to the cart            |
| `cart_remove_from_cart`               | Remove item(s) by identifier                         |
| `cart_clear_cart`                     | Empty the cart                                       |
| `cart_update_itinerary_date`          | Reschedule an itinerary item                          |
| `cart_check_user_has_payment_card`    | Whether a (tokenized) card is on file                |
| `cart_onboard_card`                   | Tokenize a card via mock VIC (card bypasses the LLM)|
| `cart_get_vic_iframe_config`         | Config for the (mock) hosted card-capture iframe     |
| `cart_request_purchase_confirmation`  | Step 1 — summarize order & ask user to confirm       |
| `cart_confirm_purchase`               | Step 2 — finalize and tokenize payment (mock)        |

Checkout is deliberately **two-step**: the agent summarizes the order and asks
for explicit confirmation before `cart_confirm_purchase` charges (mock).
Purchase-confirmation notifications will be handled by WorkIQ.

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

## REST endpoints (non-LLM, UI support)

Card and structured-data operations bypass the model entirely:

| Endpoint                              | Purpose                                     |
| ------------------------------------- | ------------------------------------------- |
| `GET  /health`                        | Liveness + model/vic flags                 |
| `POST /invocations`                   | Chat (SSE streaming)                        |
| `GET  /api/cart/{user_id}`            | Current cart (via `cart-tools` MCP)         |
| `GET  /api/itinerary/{user_id}`       | Itinerary (via Cosmos directly)             |
| `GET  /api/vic/iframe-config/{user}` | Mock card-capture iframe config             |
| `POST /api/vic/onboard-card`         | Direct card tokenization (never sent to LLM)|
