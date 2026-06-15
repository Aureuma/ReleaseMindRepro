#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR"

CONFIG="configs/paper_smoke.toml"

uv run releasemind-repro --config "$CONFIG" doctor
uv run releasemind-repro --config "$CONFIG" train-proxies
uv run releasemind-repro --config "$CONFIG" audit --skip-if-missing
uv run releasemind-repro --config "$CONFIG" evaluate-risk
uv run releasemind-repro --config "$CONFIG" simulate-routing
uv run releasemind-repro --config "$CONFIG" verify --skip-compare --strict
