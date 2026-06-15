#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="${1:-configs/paper.toml}"
shift || true

cd "$ROOT_DIR"

printf 'Running full paper reproduction with %s\n' "$CONFIG"
uv run releasemind-repro --config "$CONFIG" reproduce-paper "$@"
uv run releasemind-repro --config "$CONFIG" build-docs
uv run releasemind-repro --config "$CONFIG" verify --compare
