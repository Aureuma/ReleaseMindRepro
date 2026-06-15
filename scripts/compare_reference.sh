#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="${1:-configs/paper.toml}"

cd "$ROOT_DIR"

printf 'Rebuilding reproducibility bundle for %s\n' "$CONFIG"
uv run releasemind-repro build-docs --config "$CONFIG"
uv run releasemind-repro compare --config "$CONFIG" --strict --json
