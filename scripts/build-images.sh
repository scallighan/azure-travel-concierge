#!/usr/bin/env bash
# Build and push all five container images to GHCR with an *immutable* tag.
#
# The image tag defaults to the current git commit's short SHA (with a unique
# "-dirty-<epoch>" suffix when the working tree has uncommitted changes) so each
# build produces a distinct, content-addressable tag. Terraform then pins the
# Container Apps to that exact tag, guaranteeing a new revision (and a fresh
# image pull) on every deploy -- no more "is :latest actually the latest?".
#
# The moving ":latest" tag is *also* updated (as a human convenience pointer)
# unless PUSH_LATEST=false, but nothing in the running infrastructure relies on
# it.
#
# Requires: docker logged in to ghcr.io, GH_REPO set to "owner/name".
#
# Env:
#   GH_REPO      (required)  owner/name for the GHCR namespace
#   TAG          (optional)  override the computed immutable tag
#   PUSH_LATEST  (optional)  also push/update :latest (default: true)
#
# Prints "IMAGE_TAG=<tag>" on the last line so callers (deploy.sh) can capture
# the exact tag that was built and feed it to `terraform apply`.
set -euo pipefail

GH_REPO="${GH_REPO:?set GH_REPO=owner/name}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REG="ghcr.io/${GH_REPO}"
PUSH_LATEST="${PUSH_LATEST:-true}"

# --- Compute an immutable tag (unless one was supplied) ----------------------
if [[ -z "${TAG:-}" ]]; then
  sha="$(git -C "${ROOT}" rev-parse --short=7 HEAD 2>/dev/null || echo nogit)"
  if git -C "${ROOT}" diff --quiet 2>/dev/null && git -C "${ROOT}" diff --cached --quiet 2>/dev/null; then
    TAG="${sha}"
  else
    # Uncommitted changes: keep the tag unique so a rebuilt "dirty" image is
    # never confused with a previous one (and always triggers a new revision).
    TAG="${sha}-dirty-$(date +%s)"
  fi
fi

declare -A images=(
  ["concierge-agent"]="agents/concierge_agent"
  ["travel-tools-mcp"]="mcp-servers/travel-tools"
  ["cart-tools-mcp"]="mcp-servers/cart-tools"
  ["vic-mock-mcp"]="mcp-servers/vic-mock"
  ["merchant-mock-mcp"]="mcp-servers/merchant-mock"
)

for name in "${!images[@]}"; do
  ctx="${ROOT}/${images[$name]}"
  echo "==> Building ${REG}/${name}:${TAG} from ${ctx}"
  docker build -t "${REG}/${name}:${TAG}" "${ctx}"
  docker push "${REG}/${name}:${TAG}"
  if [[ "${PUSH_LATEST}" == "true" ]]; then
    docker tag "${REG}/${name}:${TAG}" "${REG}/${name}:latest"
    docker push "${REG}/${name}:latest"
  fi
done

echo "All images pushed to ${REG} (tag: ${TAG})."
echo "IMAGE_TAG=${TAG}"
