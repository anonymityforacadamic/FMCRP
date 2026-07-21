#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME="${1:-fmcrp}"
KNATIVE_VERSION="${KNATIVE_VERSION:-knative-v1.22.1}"
KIND_VERSION="${KIND_VERSION:-v0.32.0}"
KUBECTL_VERSION="${KUBECTL_VERSION:-v1.36.2}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS_DIR="${PROJECT_ROOT}/tools/linux"
KUBECONFIG_FILE="${PROJECT_ROOT}/.kubeconfig"

case "$(uname -m)" in
  x86_64|amd64) ARCH="amd64" ;;
  aarch64|arm64) ARCH="arm64" ;;
  *) echo "Unsupported Linux architecture: $(uname -m)" >&2; exit 1 ;;
esac

for command in docker curl sha256sum; do
  command -v "$command" >/dev/null || { echo "Required command not found: $command" >&2; exit 1; }
done
docker version --format '{{.Server.Version}}' >/dev/null

mkdir -p "$TOOLS_DIR"
KIND_BIN="${TOOLS_DIR}/kind"
KUBECTL_BIN="${TOOLS_DIR}/kubectl"
if [[ ! -x "$KIND_BIN" ]]; then
  curl --fail --location --silent --show-error \
    "https://kind.sigs.k8s.io/dl/${KIND_VERSION}/kind-linux-${ARCH}" \
    --output "$KIND_BIN"
  chmod 0755 "$KIND_BIN"
fi
if [[ ! -x "$KUBECTL_BIN" ]]; then
  curl --fail --location --silent --show-error \
    "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${ARCH}/kubectl" \
    --output "$KUBECTL_BIN"
  curl --fail --location --silent --show-error \
    "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${ARCH}/kubectl.sha256" \
    --output "${KUBECTL_BIN}.sha256"
  expected_hash="$(tr -d '[:space:]' < "${KUBECTL_BIN}.sha256")"
  actual_hash="$(sha256sum "$KUBECTL_BIN" | awk '{print $1}')"
  [[ "$actual_hash" == "$expected_hash" ]] || { rm -f "$KUBECTL_BIN"; echo "kubectl checksum verification failed." >&2; exit 1; }
  chmod 0755 "$KUBECTL_BIN"
fi

export KUBECONFIG="$KUBECONFIG_FILE"
if ! "$KIND_BIN" get clusters | grep --fixed-strings --line-regexp --quiet "$CLUSTER_NAME"; then
  "$KIND_BIN" create cluster --name "$CLUSTER_NAME" --wait 5m --kubeconfig "$KUBECONFIG_FILE"
else
  "$KIND_BIN" export kubeconfig --name "$CLUSTER_NAME" --kubeconfig "$KUBECONFIG_FILE"
fi

"$KUBECTL_BIN" apply -f "https://github.com/knative/serving/releases/download/${KNATIVE_VERSION}/serving-crds.yaml"
"$KUBECTL_BIN" apply -f "https://github.com/knative/serving/releases/download/${KNATIVE_VERSION}/serving-core.yaml"
"$KUBECTL_BIN" apply -f "https://github.com/knative-extensions/net-kourier/releases/download/${KNATIVE_VERSION}/kourier.yaml"
"$KUBECTL_BIN" patch configmap/config-network --namespace knative-serving --type merge --patch '{"data":{"ingress-class":"kourier.ingress.networking.knative.dev"}}'
"$KUBECTL_BIN" wait --for=condition=Ready pod --all --namespace knative-serving --timeout=5m
"$KUBECTL_BIN" wait --for=condition=Ready pod --all --namespace kourier-system --timeout=5m

echo "Cluster and Knative are ready. Run: bash scripts/deploy.sh"
