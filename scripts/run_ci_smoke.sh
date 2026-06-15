#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR"

CONFIG="configs/paper_smoke.toml"

uv run releasemind-repro doctor --config "$CONFIG"
uv run releasemind-repro train-proxies --config "$CONFIG"
uv run releasemind-repro audit --config "$CONFIG" --skip-if-missing
uv run releasemind-repro evaluate-risk --config "$CONFIG"
uv run releasemind-repro simulate-routing --config "$CONFIG"
uv run releasemind-repro verify --config "$CONFIG" --skip-compare --strict
