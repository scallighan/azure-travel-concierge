#!/usr/bin/env bash
# End-to-end deploy: build images -> terraform apply -> seed data -> ingest docs.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GH_REPO="${GH_REPO:?set GH_REPO=owner/name}"

# Immutable image tag for this deploy: the current commit SHA (with a unique
# "-dirty-<epoch>" suffix when the tree has uncommitted changes). Both the build
# and `terraform apply` below use this exact tag, so the Container Apps are
# pinned to the images we just built -- a new tag always forces a fresh revision
# and image pull (no reliance on a mutable ":latest").
if [[ -z "${TAG:-}" ]]; then
  _sha="$(git -C "${ROOT}" rev-parse --short=7 HEAD 2>/dev/null || echo nogit)"
  if git -C "${ROOT}" diff --quiet 2>/dev/null && git -C "${ROOT}" diff --cached --quiet 2>/dev/null; then
    TAG="${_sha}"
  else
    TAG="${_sha}-dirty-$(date +%s)"
  fi
fi
export TAG
echo "== Image tag for this deploy: ${TAG} =="

echo "== 1/5 Build & push container images =="
"${ROOT}/scripts/build-images.sh"

echo "== 2/5 Terraform apply =="
cd "${ROOT}/terraform"
# Persist the tag so a subsequent *manual* `terraform apply` (e.g. an infra-only
# change) keeps the apps pinned to the last-deployed images instead of resetting
# them to ":latest". `-var` below still wins for this run.
printf 'container_image_tag = "%s"\n' "${TAG}" > "${ROOT}/terraform/image.auto.tfvars"
terraform init -input=false
terraform apply -auto-approve -var "gh_repo=${GH_REPO}" -var "container_image_tag=${TAG}"

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
