#!/usr/bin/env bash
# Build and push all four container images to GHCR.
# Requires: docker logged in to ghcr.io, GH_REPO set to "owner/name".
set -euo pipefail

GH_REPO="${GH_REPO:?set GH_REPO=owner/name}"
TAG="${TAG:-latest}"
REG="ghcr.io/${GH_REPO}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

declare -A images=(
  ["concierge-agent"]="agents/concierge_agent"
  ["travel-tools-mcp"]="mcp-servers/travel-tools"
  ["cart-tools-mcp"]="mcp-servers/cart-tools"
  ["vic-mock-mcp"]="mcp-servers/vic-mock"
)

for name in "${!images[@]}"; do
  ctx="${ROOT}/${images[$name]}"
  echo "==> Building ${REG}/${name}:${TAG} from ${ctx}"
  docker build -t "${REG}/${name}:${TAG}" "${ctx}"
  docker push "${REG}/${name}:${TAG}"
done

echo "All images pushed to ${REG}."
