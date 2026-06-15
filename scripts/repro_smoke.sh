#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="${1:-configs/paper_smoke.toml}"

cd "$ROOT_DIR"

printf 'Running reproducibility smoke flow with %s\n' "$CONFIG"
uv run releasemind-repro --config "$CONFIG" doctor
uv run releasemind-repro --config "$CONFIG" train-proxies
uv run releasemind-repro --config "$CONFIG" audit --skip-if-missing
uv run releasemind-repro --config "$CONFIG" evaluate-risk
uv run releasemind-repro --config "$CONFIG" simulate-routing
uv run releasemind-repro --config "$CONFIG" verify --strict

if [ -f artifacts/reference/manifest.json ]; then
  uv run releasemind-repro --config "$CONFIG" compare --strict
fi
