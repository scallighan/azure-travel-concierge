#!/usr/bin/env bash
# Run the full Travel Concierge stack locally as host processes (no Docker).
#
# Uses your host `az login` session for Azure auth (DefaultAzureCredential),
# so no service principal is required. `travel-tools` and `vic-mock` run as
# self-contained mocks; the agent + `cart-tools` still need a real Azure AI
# Foundry endpoint and Cosmos DB account (see docs/DEPLOYMENT.md).
#
# Config is read from a .env file at the repo root (copy .env.local.example).
#
# Usage:
#   ./scripts/run-local.sh          # start the four backend services
#   ./scripts/run-local.sh --ui     # also start the Vite web UI
#   Ctrl-C to stop everything.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="${ROOT}/.venv-local"
LOG_DIR="${ROOT}/.local-logs"
START_UI=false
[[ "${1:-}" == "--ui" ]] && START_UI=true

# --- Load .env --------------------------------------------------------------
if [[ -f "${ROOT}/.env" ]]; then
  echo "==> Loading ${ROOT}/.env"
  set -a; # shellcheck disable=SC1091
  source "${ROOT}/.env"; set +a
else
  echo "!! No .env found. Copy .env.local.example to .env and fill it in." >&2
  exit 1
fi

# --- Validate required config ----------------------------------------------
: "${AZURE_AI_PROJECT_ENDPOINT:?set AZURE_AI_PROJECT_ENDPOINT in .env}"
: "${COSMOS_ENDPOINT:?set COSMOS_ENDPOINT in .env}"
export AZURE_AI_MODEL_DEPLOYMENT_NAME="${AZURE_AI_MODEL_DEPLOYMENT_NAME:-gpt-4o}"
export COSMOS_DATABASE="${COSMOS_DATABASE:-concierge}"
export ENABLE_VIC_INTEGRATION="${ENABLE_VIC_INTEGRATION:-true}"

if ! az account show >/dev/null 2>&1; then
  echo "!! Not logged in to Azure. Run 'az login' first." >&2
  exit 1
fi

# --- Python venv with all service requirements ------------------------------
if [[ ! -d "${VENV}" ]]; then
  echo "==> Creating venv at ${VENV}"
  python3 -m venv "${VENV}"
fi
# shellcheck disable=SC1091
source "${VENV}/bin/activate"
echo "==> Installing dependencies (first run may take a minute)"
pip install --quiet --upgrade pip
pip install --quiet \
  -r "${ROOT}/mcp-servers/vic-mock/requirements.txt" \
  -r "${ROOT}/mcp-servers/travel-tools/requirements.txt" \
  -r "${ROOT}/mcp-servers/cart-tools/requirements.txt" \
  -r "${ROOT}/agents/concierge_agent/requirements.txt"

mkdir -p "${LOG_DIR}"
PIDS=()

cleanup() {
  echo; echo "==> Stopping services..."
  for pid in "${PIDS[@]:-}"; do
    [[ -n "${pid}" ]] && kill "${pid}" 2>/dev/null || true
  done
  wait 2>/dev/null || true
  echo "Done."
}
trap cleanup INT TERM EXIT

start() {
  local name="$1" dir="$2" port="$3" cmd="$4"
  echo "==> ${name} on :${port}  (logs: ${LOG_DIR}/${name}.log)"
  ( cd "${dir}" && PORT="${port}" bash -c "${cmd}" ) >"${LOG_DIR}/${name}.log" 2>&1 &
  PIDS+=("$!")
}

# --- Mock MCP servers -------------------------------------------------------
start "vic-mock"    "${ROOT}/mcp-servers/vic-mock"    8083 "python server.py"

start "travel-tools" "${ROOT}/mcp-servers/travel-tools" 8081 "python server.py"

# --- Cosmos-backed cart MCP -------------------------------------------------
start "cart-tools"   "${ROOT}/mcp-servers/cart-tools"   8082 \
  "VIC_MCP_URL=http://localhost:8083/mcp python server.py"

# --- Supervisor agent -------------------------------------------------------
start "concierge-agent" "${ROOT}/agents/concierge_agent" 8080 \
  "TRAVEL_MCP_URL=http://localhost:8081/mcp CART_MCP_URL=http://localhost:8082/mcp python app.py"

# --- Wait for the agent to become healthy -----------------------------------
echo "==> Waiting for the agent health check..."
for _ in $(seq 1 30); do
  if curl -fsS http://localhost:8080/health >/dev/null 2>&1; then
    echo "    agent is healthy: http://localhost:8080/health"
    break
  fi
  sleep 1
done

# --- Optional web UI --------------------------------------------------------
if [[ "${START_UI}" == true ]]; then
  echo "==> Starting web UI on http://localhost:5173"
  ( cd "${ROOT}/web-ui" \
    && VITE_AGENT_URL="http://localhost:8080" \
       VITE_MOCK_AUTH="true" \
       VITE_ENABLE_VIC="${ENABLE_VIC_INTEGRATION}" \
       VITE_DEMO_USER_ID="${VITE_DEMO_USER_ID:-demo-user}" \
       bash -c "npm install --silent && npm run dev -- --host" ) \
    >"${LOG_DIR}/web-ui.log" 2>&1 &
  PIDS+=("$!")
fi

echo
echo "Stack is up:"
echo "  agent          http://localhost:8080  (/health, /invocations)"
echo "  travel-tools   http://localhost:8081/mcp"
echo "  cart-tools     http://localhost:8082/mcp"
echo "  vic-mock      http://localhost:8083/mcp"
[[ "${START_UI}" == true ]] && echo "  web-ui         http://localhost:5173"
echo
echo "Try:  curl -N localhost:8080/invocations -H 'content-type: application/json' \\"
echo "        -d '{\"prompt\":\"Plan a 3-day trip to Rome\",\"user_id\":\"demo-user\",\"session_id\":\"s1\"}'"
echo
echo "Tailing logs. Press Ctrl-C to stop."
tail -n +1 -f "${LOG_DIR}"/*.log
