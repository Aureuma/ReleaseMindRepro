# ⚡ Quickstart

## 🚦 Minimum path (smoke config)

```bash
cd ReleaseMindRepro
uv sync
uv run releasemind-repro --config configs/paper_smoke.toml doctor
uv run releasemind-repro --config configs/paper_smoke.toml reproduce-paper --json
```

## 🧪 Smoke run with checkpoints

1. Verify schema checks:

```bash
uv run releasemind-repro --config configs/paper_smoke.toml verify --strict
```

2. Compare against reference manifest if present:

```bash
uv run releasemind-repro --config configs/paper_smoke.toml compare --strict --json
```

## 🧭 Full paper path

```bash
uv run releasemind-repro --config configs/paper.toml doctor
uv run releasemind-repro --config configs/paper.toml reproduce-paper --publish-paper-layout --json
uv run releasemind-repro --config configs/paper.toml build-docs
```

## 📈 Expected outputs

- `outputs/risk_proxy/smartnote_proxy.parquet`
- `outputs/risk_proxy/rnsum_proxy.parquet`
- `outputs/audit/oracle_audit.jsonl`
- `outputs/eval/risk_control_summary.csv`
- `outputs/routing/simulate_routing.csv`
- `outputs/figures/*.pdf`
- `artifacts/reference/manifest.json`
