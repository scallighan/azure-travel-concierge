# Deployment Guide

End-to-end provisioning of the Azure Travel Concierge on Azure AI Foundry using
Terraform, container images on GHCR, and Azure Static Web Apps for the UI.

## Prerequisites

| Tool                | Purpose                                            |
| ------------------- | -------------------------------------------------- |
| Azure CLI (`az`)    | Auth + subscription selection (`az login`)         |
| Terraform ≥ 1.6     | Infrastructure provisioning                        |
| Docker              | Building the five container images                 |
| GitHub account/PAT  | Pushing images to GHCR (`ghcr.io/<owner>/<repo>`)  |
| Node.js ≥ 18 + npm  | Building the React web UI                          |
| Python ≥ 3.11       | Seed + AI Search ingestion scripts                 |

You also need:
- An Azure subscription with quota for the chosen Foundry model (`gpt-5.4` by
  default; override via `chat_model`).
- Permission to create Entra app registrations and role assignments.

## 1. Build & push container images

Images: `concierge-agent`, `travel-tools-mcp`, `cart-tools-mcp`, `vic-mock-mcp`,
`merchant-mock-mcp`.

```bash
export GH_REPO="your-org/travel-concierge-azure"   # ghcr.io namespace
echo "$GHCR_PAT" | docker login ghcr.io -u <you> --password-stdin
./scripts/build-images.sh                          # builds + pushes :latest
```

> Make the GHCR packages public, or grant the Container Apps environment pull
> access, so Azure can pull the images.

## 2. Provision infrastructure with Terraform

```bash
cd terraform
cp terraform.tfvars.sample terraform.tfvars   # then edit values
terraform init
terraform apply -var "gh_repo=${GH_REPO}"
```

Key variables (`terraform.tfvars`):

- `subscription_id` — target Azure subscription
- `location` — e.g. `EastUS2`
- `gh_repo` — GHCR image namespace (`owner/name`)
- Optional: `chat_model`, `embedding_model`, `enable_vic_integration`,
  `container_image_tag`
- Reuse an existing AI Search service (saves cost/capacity): set
  `use_existing_search = true` and `existing_search_service_name`
  (and `existing_search_resource_group_name` if it lives in another RG).

This creates: Resource Group, Log Analytics + App Insights, Storage, Key Vault,
**AI Foundry** account/project + model deployments, **Cosmos DB** (5 containers,
incl. per-itinerary `chatHistory`), **AI Search** (unless reusing an existing
service), the VNet + **private endpoints** for Cosmos/Storage/Key Vault, the
**Container Apps** environment + 4 apps, the **Entra SPA** app registration, and a
**Static Web App**. All data-plane access is via a **User-Assigned Managed
Identity** (no keys; Storage shared keys are disabled).

> **Foundry tracing** — Application Insights is connected to the Foundry account
> and project (an `AppInsights` connection, plus Log Analytics/Monitoring Data
> Reader roles for the project identity), so agent runs and GenAI traces show up
> in the Foundry portal's tracing view with no extra setup.

> **vic-mock and merchant-mock are stateful** — the mock VIC server keeps
> token/mandate/card state in-memory (and indexes cards by `user_id`), and the
> mock merchant keeps orders in-memory, to mirror the real VTS/VACP + acquirer
> flow. Each must run as a **single replica**. Do not scale `vic-mock-mcp` or
> `merchant-mock-mcp` beyond one instance.

> **Foundry Toolbox** — the travel skills and payments agent consume the
> `travel-concierge-toolbox` (WebIQ + VIC tools). Set `foundry_toolbox_name` /
> `foundry_toolbox_version` in `terraform.tfvars` (or leave the version blank to
> resolve the default at startup). Without it, skills fall back to web search and
> payments to the local cart/VIC MCP.

## 3. Seed demo data & ingest visa docs

> **Private networking:** Cosmos DB and Storage have public access disabled, so
> these scripts must run from within (or peered to) the deployment VNet. Also
> approve the AI Search → Storage shared private link once before ingesting:
> `az storage account private-endpoint-connection approve --account-name <sa> --resource-group <rg> --name <connection-name>`.

```bash
cd terraform
export COSMOS_ENDPOINT="$(terraform output -raw cosmos_endpoint)"
export COSMOS_DATABASE="$(terraform output -raw cosmos_database)"
python ../scripts/seed_demo_data.py

export SEARCH_ENDPOINT="$(terraform output -raw search_endpoint)"
export SEARCH_INDEX_NAME="$(terraform output -raw search_index_name)"
python ../search-ingestion/ingest.py
```

> These scripts authenticate with `DefaultAzureCredential` — run them as an
> identity that holds the Cosmos Data Contributor and Search Index Data
> Contributor roles (add a role assignment for your user if needed).

## 4. Build & deploy the web UI

A freshly-provisioned Static Web App stays in **"Waiting for deployment"** until
content is pushed to it. Use the helper script, which reads all configuration
from terraform outputs, builds the SPA, and publishes the bundle:

```bash
./scripts/deploy-webui.sh
```

It wires `VITE_AGENT_URL`, `VITE_ENTRA_CLIENT_ID`, and `VITE_ENTRA_TENANT_ID`
from terraform outputs and picks real Entra auth when a client id is present
(export `VITE_MOCK_AUTH=true` to force mock auth for a quick demo).

<details>
<summary>Manual equivalent</summary>

```bash
cd web-ui
cp .env.example .env
# populate from terraform outputs:
#   VITE_AGENT_URL         = terraform output -raw agent_url
#   VITE_ENTRA_CLIENT_ID   = terraform output -raw webui_entra_client_id
#   VITE_ENTRA_TENANT_ID   = terraform output -raw webui_entra_tenant_id
#   VITE_MOCK_AUTH=false   (set true to skip Entra for a quick demo)
npm install
npm run build

# Deploy the static bundle to the provisioned Static Web App:
npx @azure/static-web-apps-cli deploy ./dist \
  --deployment-token "$(terraform -chdir=../terraform output -raw static_web_app_api_key)"
```

</details>

## One-shot deploy

`scripts/deploy.sh` runs the full pipeline in sequence (build → apply → seed →
ingest → deploy UI) and prints the agent URL, Static Web App hostname, and Entra
client id:

```bash
export GH_REPO="your-org/travel-concierge-azure"
./scripts/deploy.sh
```

## Local development

Two ways to run the whole stack (agent + 4 MCP servers + optional UI) locally.
`travel-tools`, `vic-mock` and `merchant-mock` run as self-contained mocks; the
agent and `cart-tools` still need a real **Azure AI Foundry** endpoint and
**Cosmos DB** account (the LLM and Cosmos cannot be mocked).

First, create your config:

```bash
cp .env.local.example .env   # then fill in Foundry + Cosmos endpoints
```

### Option A — host processes (uses your `az login`)

```bash
az login
./scripts/run-local.sh        # add --ui to also start the Vite web UI
```

This creates a venv, installs all five services' requirements, launches them on
ports 8080 (agent), 8081 (travel), 8082 (cart), 8083 (vic), 8084 (merchant),
health-checks the agent, and tails logs. Ctrl-C stops everything.

### Option B — docker compose

The slim container images have no `az` CLI, so provide a service principal
(`AZURE_CLIENT_ID` / `AZURE_TENANT_ID` / `AZURE_CLIENT_SECRET`) in `.env` with
Cosmos Data Contributor + Foundry roles.

```bash
docker compose up --build                 # backends only
docker compose --profile ui up --build    # backends + web UI on :5173
```

### Manual (individual shells)

Set the env vars from `agents/concierge_agent/config.py`
(`AZURE_AI_PROJECT_ENDPOINT`, `TRAVEL_MCP_URL`, `CART_MCP_URL`,
`COSMOS_ENDPOINT`, `SEARCH_ENDPOINT`, …), sign in with `az login`, then:

```bash
# terminal 1-4: MCP servers
PORT=8083 python mcp-servers/vic-mock/server.py
PORT=8084 python mcp-servers/merchant-mock/server.py
PORT=8081 python mcp-servers/travel-tools/server.py
PORT=8082 VIC_MCP_URL=http://localhost:8083/mcp MERCHANT_MCP_URL=http://localhost:8084/mcp python mcp-servers/cart-tools/server.py
# terminal 5: agent (from agents/concierge_agent)
TRAVEL_MCP_URL=http://localhost:8081/mcp CART_MCP_URL=http://localhost:8082/mcp uvicorn app:app --port 8080
# terminal 5: UI (VITE_MOCK_AUTH=true, VITE_AGENT_URL=http://localhost:8080)
cd web-ui && npm run dev
```

## Teardown

```bash
cd terraform && terraform destroy -var "gh_repo=${GH_REPO}"
```
