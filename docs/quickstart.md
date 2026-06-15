# Quickstart

## Minimum reproducibility path

```bash
cd ReleaseMindRepro
uv sync
uv run releasemind-repro doctor --config configs/paper_smoke.toml
uv run releasemind-repro reproduce-paper --config configs/paper_smoke.toml --json
```

## Smoke path with explicit checkpoints

1. Verify base schema checks:

```bash
uv run releasemind-repro verify --config configs/paper_smoke.toml --strict
```

2. Compare against the reference manifest if present:

```bash
uv run releasemind-repro compare --config configs/paper_smoke.toml --strict --json
```

## Full paper path

```bash
uv run releasemind-repro doctor --config configs/paper.toml
uv run releasemind-repro reproduce-paper --config configs/paper.toml --publish-paper-layout --json
uv run releasemind-repro build-docs --config configs/paper.toml
```

## Expected outputs

- `outputs/risk_proxy/smartnote_proxy.parquet`
- `outputs/risk_proxy/rnsum_proxy.parquet`
- `outputs/audit/oracle_audit.jsonl`
- `outputs/eval/risk_control_summary.csv`
- `outputs/routing/simulate_routing.csv`
- `outputs/figures/*.pdf`
- `artifacts/reference/manifest.json`
