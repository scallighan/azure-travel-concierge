#!/usr/bin/env bash
# End-to-end deploy: build images -> terraform apply -> seed data -> ingest docs.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GH_REPO="${GH_REPO:?set GH_REPO=owner/name}"

echo "== 1/5 Build & push container images =="
"${ROOT}/scripts/build-images.sh"

echo "== 2/5 Terraform apply =="
cd "${ROOT}/terraform"
terraform init -input=false
terraform apply -auto-approve -var "gh_repo=${GH_REPO}"

echo "== 3/5 Seed demo data =="
export COSMOS_ENDPOINT="$(terraform output -raw cosmos_endpoint)"
export COSMOS_DATABASE="$(terraform output -raw cosmos_database)"
python "${ROOT}/scripts/seed_demo_data.py"

echo "== 4/5 Ingest visa documentation into AI Search =="
export SEARCH_ENDPOINT="$(terraform output -raw search_endpoint)"
export SEARCH_INDEX_NAME="$(terraform output -raw search_index_name)"
python "${ROOT}/search-ingestion/ingest.py"

echo "== 5/5 Build & deploy the web UI to Static Web Apps =="
"${ROOT}/scripts/deploy-webui.sh"

echo
echo "Done. Agent URL:      $(terraform output -raw agent_url)"
echo "Static Web App:       $(terraform output -raw static_web_app_hostname)"
echo "Entra client id:      $(terraform output -raw webui_entra_client_id)"
