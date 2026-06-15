#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="${1:-configs/paper.toml}"
shift || true

cd "$ROOT_DIR"

printf 'Running full paper reproduction with %s\n' "$CONFIG"
uv run releasemind-repro reproduce-paper --config "$CONFIG" "$@"
uv run releasemind-repro build-docs --config "$CONFIG"
uv run releasemind-repro verify --config "$CONFIG" --compare
