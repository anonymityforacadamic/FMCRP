#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME="${1:-fmcrp}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KIND_BIN="${PROJECT_ROOT}/tools/linux/kind"

[[ -x "$KIND_BIN" ]] || { echo "Repository-local kind binary not found." >&2; exit 1; }
read -r -p "Delete kind cluster '${CLUSTER_NAME}'? [y/N] " answer
case "$answer" in
  y|Y|yes|YES) "$KIND_BIN" delete cluster --name "$CLUSTER_NAME" ;;
  *) echo "Cancelled." ;;
esac
