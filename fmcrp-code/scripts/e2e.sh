#!/usr/bin/env bash
set -euo pipefail

CONTROLLER_PORT="${1:-18080}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KUBECTL_BIN="${PROJECT_ROOT}/tools/linux/kubectl"
export KUBECONFIG="${PROJECT_ROOT}/.kubeconfig"
export PYTHONPATH="${PROJECT_ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"

[[ -x "$KUBECTL_BIN" ]] || { echo "Run bash scripts/bootstrap.sh and bash scripts/deploy.sh first." >&2; exit 1; }
command -v python3 >/dev/null || { echo "python3 is required." >&2; exit 1; }
command -v curl >/dev/null || { echo "curl is required." >&2; exit 1; }

cd "$PROJECT_ROOT"
python3 -m unittest discover -s tests -v
"$KUBECTL_BIN" port-forward --namespace fmcrp svc/fmcrp-controller "${CONTROLLER_PORT}:8080" >/tmp/fmcrp-port-forward.log 2>&1 &
FORWARD_PID=$!
cleanup() { kill "$FORWARD_PID" 2>/dev/null || true; wait "$FORWARD_PID" 2>/dev/null || true; }
trap cleanup EXIT

for _ in $(seq 1 30); do
  if curl --fail --silent "http://127.0.0.1:${CONTROLLER_PORT}/healthz" >/dev/null; then break; fi
  sleep 1
done
curl --fail --silent --show-error \
  --request POST "http://127.0.0.1:${CONTROLLER_PORT}/schedule" \
  --header 'Content-Type: application/json' \
  --data-binary @examples/request.json
echo
"$KUBECTL_BIN" get ksvc fmcrp-target --namespace fmcrp
"$KUBECTL_BIN" run fmcrp-knative-smoke --rm -i --restart=Never --namespace fmcrp \
  --image=curlimages/curl:8.12.1 -- curl --fail --silent --show-error http://fmcrp-target.fmcrp.svc.cluster.local
echo
