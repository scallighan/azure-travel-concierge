#!/usr/bin/env bash
# Build the React web UI with values from terraform outputs and deploy the
# static bundle to the provisioned Azure Static Web App.
#
# A freshly-created Static Web App sits in "Waiting for deployment" until content
# is pushed to it; this script performs that first (and every subsequent) deploy.
#
# Requires: node + npm, and either the Azure SWA CLI (via npx) available.
# Reads all configuration from `terraform output`, so run `terraform apply` first.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TF_DIR="${ROOT}/terraform"
UI_DIR="${ROOT}/web-ui"

tf() { terraform -chdir="${TF_DIR}" output -raw "$1"; }

# Fail early with a clear message if terraform state/outputs aren't available
# (e.g. run before `terraform apply`, or from the wrong directory).
if ! terraform -chdir="${TF_DIR}" output agent_url >/dev/null 2>&1; then
  echo "ERROR: could not read terraform outputs from ${TF_DIR}." >&2
  echo "       Run 'terraform apply' first (outputs are read straight from state)." >&2
  exit 1
fi

echo "== Reading terraform outputs =="
AGENT_URL="$(tf agent_url)"
ENTRA_CLIENT_ID="$(tf webui_entra_client_id)"
ENTRA_TENANT_ID="$(tf webui_entra_tenant_id)"
DEPLOY_TOKEN="$(tf static_web_app_api_key)"
SWA_HOSTNAME="$(tf static_web_app_hostname)"
ENABLE_VIC="$(tf enable_vic_integration 2>/dev/null || echo true)"

# Use real Entra auth when a client id is present; otherwise fall back to mock
# auth so the demo still works. Override by exporting VITE_MOCK_AUTH.
if [[ -n "${VITE_MOCK_AUTH:-}" ]]; then
  MOCK_AUTH="${VITE_MOCK_AUTH}"
elif [[ -n "${ENTRA_CLIENT_ID}" ]]; then
  MOCK_AUTH="false"
else
  MOCK_AUTH="true"
fi

echo "== Building web UI =="
echo "   Agent URL:   ${AGENT_URL}"
echo "   Mock auth:   ${MOCK_AUTH}"
echo "   VIC enabled: ${ENABLE_VIC}"

cd "${UI_DIR}"
npm install

VITE_AGENT_URL="${AGENT_URL}" \
VITE_ENTRA_CLIENT_ID="${ENTRA_CLIENT_ID}" \
VITE_ENTRA_TENANT_ID="${ENTRA_TENANT_ID}" \
VITE_ENABLE_VIC="${ENABLE_VIC}" \
VITE_MOCK_AUTH="${MOCK_AUTH}" \
  npm run build

echo "== Deploying to Azure Static Web App =="
npx --yes @azure/static-web-apps-cli deploy ./dist \
  --deployment-token "${DEPLOY_TOKEN}" \
  --env production

echo
echo "Web UI deployed: ${SWA_HOSTNAME}"
