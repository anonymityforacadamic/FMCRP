#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME="${1:-fmcrp}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS_DIR="${PROJECT_ROOT}/tools/linux"
KIND_BIN="${TOOLS_DIR}/kind"
KUBECTL_BIN="${TOOLS_DIR}/kubectl"
export KUBECONFIG="${PROJECT_ROOT}/.kubeconfig"

[[ -x "$KIND_BIN" && -x "$KUBECTL_BIN" ]] || { echo "Run bash scripts/bootstrap.sh first." >&2; exit 1; }
command -v docker >/dev/null || { echo "Docker is required." >&2; exit 1; }
docker version --format '{{.Server.Version}}' >/dev/null

cd "$PROJECT_ROOT"
docker build --tag fmcrp-controller:0.1.0 --file Dockerfile.controller .
docker build --tag fmcrp-target:0.1.0 ./function
"$KIND_BIN" load docker-image fmcrp-controller:0.1.0 fmcrp-target:0.1.0 --name "$CLUSTER_NAME"
"$KUBECTL_BIN" apply -f deploy/namespace.yaml
"$KUBECTL_BIN" apply -f deploy/controller.yaml
"$KUBECTL_BIN" apply -f deploy/function.yaml
"$KUBECTL_BIN" rollout status deployment/fmcrp-controller --namespace fmcrp --timeout=3m
"$KUBECTL_BIN" wait --for=condition=Ready ksvc/fmcrp-target --namespace fmcrp --timeout=5m

echo "Deployment is ready. Run: bash scripts/e2e.sh"
