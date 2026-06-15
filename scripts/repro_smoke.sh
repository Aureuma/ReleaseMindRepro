#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="${1:-configs/paper_smoke.toml}"

cd "$ROOT_DIR"

printf 'Running reproducibility smoke flow with %s\n' "$CONFIG"
uv run releasemind-repro doctor --config "$CONFIG"
uv run releasemind-repro train-proxies --config "$CONFIG"
uv run releasemind-repro audit --config "$CONFIG" --skip-if-missing
uv run releasemind-repro evaluate-risk --config "$CONFIG"
uv run releasemind-repro simulate-routing --config "$CONFIG"
uv run releasemind-repro verify --config "$CONFIG" --strict

if [ -f artifacts/reference/manifest.json ]; then
  uv run releasemind-repro compare --config "$CONFIG" --strict
fi
