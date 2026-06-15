# ReleaseMindRepro

Reproducibility package for the ReleaseMind paper (`Aureuma/ReleaseMindPaper`).

This repository contains the public artifacts and executable pipeline needed to
reproduce all reported quantitative results from the paper on commodity CPU hardware.

## What is in this repository

- `releasemind_repro` — Python package with a reproducible CLI.
- `configs/paper.toml` — pinned paper defaults (sampling, thresholds, costs).
- `data/` — public fixtures and lightweight local caches.
- `artifacts/` — reference outputs used for regression checks.
- `outputs/` — default location for generated artifacts.
- `docs/` — reproducibility instructions and documentation.
- `tests/` — parser and utility checks for deterministic behavior.

## Quick start

```bash
cd ReleaseMindRepro

# Install from source
uv sync

# Check environment and tool availability
uv run releasemind-repro doctor

# Prepare paper config and show defaults
uv run releasemind-repro doctor --config configs/paper.toml
```

## One-step paper reproduction (reported results)

```bash
uv run releasemind-repro reproduce-paper --config configs/paper.toml
```

This command runs:

1. TF-IDF SmartNote proxy training (`data/smartnote_proxy.parquet`)
2. RNSum proxy construction (`data/rnsum_proxy.parquet`) from `rnsum_with_text`
3. Gemini audit for the full paper sample
4. Risk-control sweep and coverage/risk tables
5. Cost–risk simulation and plots
6. Reference comparison against committed paper outputs

## Reproduce commands

```bash
uv run releasemind-repro train-proxies --config configs/paper.toml
uv run releasemind-repro audit --config configs/paper.toml --provider gemini --sample-size 3000 --max-workers 5 --min-interval 0.4
uv run releasemind-repro evaluate-risk --config configs/paper.toml --compare-corrections
uv run releasemind-repro simulate-routing --config configs/paper.toml
```

## Environment variables

- `GOOGLE_API_KEY` or `GEMINI_API_KEY`: Gemini API key for oracle audits.
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`: optional
  for Bedrock-based fallback audit provider.
- Never store secrets in this repo.

## Datasets and data policy

- RNSum source: `https://github.com/nlab-mpg/RNSum-Dataset` (CC BY 4.0).
- SmartNote source: `https://github.com/osslab-pku/SmartNote` and
  Figshare replication package (CC BY 4.0).
- Replication artifacts are tracked only as references for reproducibility checks.
- Large external downloads (SmartNote replication zip, full RNSum text snapshot) are
  not bundled by default.

## Expected outputs

- `outputs/eval/risk_control_summary.csv`
- `outputs/eval/risk_control_summary.meta.json`
- `outputs/routing/simulate_routing.csv`
- `outputs/figures/risk_control_curve_rnsum.pdf`
- `outputs/figures/risk_control_curve_smartnote.pdf`
- `outputs/figures/routing_cost_risk_rnsum.pdf`
- `outputs/figures/routing_cost_risk_smartnote.pdf`

For exact reference outputs used in the paper, see
`artifacts/reference/`.

## License

Code and docs in this repository are released under the repository-level
license for this reproducibility package.
Datasets and upstream code remain under their original upstream terms.
