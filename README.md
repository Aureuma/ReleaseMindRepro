# 🔬 ReleaseMindRepro

Reproducibility package for the ReleaseMind paper (`Aureuma/ReleaseMindPaper`).

This repo contains the public artifacts and executable pipeline to reproduce the
paper’s quantitative results on commodity CPU hardware.

## 📦 What’s included

- `src/releasemind_repro/` — CLI package and reproducibility engine.
- `configs/paper.toml` — paper defaults for sampling, thresholds, and cost model.
- `data/` — bundled fixtures and cached source inputs.
- `outputs/` — generated artifacts from command runs.
- `artifacts/` — reference manifest bundle for verification.
- `docs/` — setup and reproducibility instructions.
- `tests/` — command/config validation coverage.

## ⚡ Quick start

```bash
cd ReleaseMindRepro
uv sync
uv run releasemind-repro --config configs/paper.toml doctor
uv run releasemind-repro --config configs/paper.toml doctor --json
```

## 📚 One-command paper reproduction

```bash
uv run releasemind-repro --config configs/paper.toml reproduce-paper
```

This runs:

1. SmartNote proxy training (`outputs/risk_proxy/smartnote_proxy.parquet`)
2. RNSum proxy construction (`outputs/risk_proxy/rnsum_proxy.parquet`)
3. Oracle audit over sampled rows
4. Risk-control evaluation and coverage/risk tables
5. Cost–risk routing simulation + plots
6. Reference comparison against committed artifacts

## 🧪 Command recipes

```bash
uv run releasemind-repro --config configs/paper.toml train-proxies
uv run releasemind-repro --config configs/paper.toml audit --provider gemini --sample-size 3000 --max-workers 5 --min-interval 0.4
uv run releasemind-repro --config configs/paper.toml evaluate-risk --compare-corrections
uv run releasemind-repro --config configs/paper.toml simulate-routing
```

## 🔑 Environment variables

- `GOOGLE_API_KEY` or `GEMINI_API_KEY`: Gemini API key for oracle audits.
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`: optional
  Bedrock fallback credentials.
- Never store secrets in this repository.

## 📁 Dataset policy

- RNSum source: `https://github.com/nlab-mpg/RNSum-Dataset` (CC BY 4.0).
- SmartNote source: `https://github.com/osslab-pku/SmartNote` (+ replication
  package, CC BY 4.0).
- Upstream datasets are not bundled in full; only lightweight fixtures are stored.

## 📈 Expected outputs

- `outputs/eval/risk_control_summary.csv`
- `outputs/eval/risk_control_summary.meta.json`
- `outputs/routing/simulate_routing.csv`
- `outputs/figures/risk_control_curve_rnsum.pdf`
- `outputs/figures/risk_control_curve_smartnote.pdf`
- `outputs/figures/routing_cost_risk_rnsum.pdf`
- `outputs/figures/routing_cost_risk_smartnote.pdf`

Reference bundle (required for strict reproducibility checks):
`artifacts/reference/`

## 🧭 Canonical invocation pattern

Prefer this order in commands and scripts:

```bash
uv run releasemind-repro --config <path> <command>
```

`<command> --config <path>` is still supported for backward compatibility.

## 📜 License

Code and docs in this repository are licensed under the repository-level license
for this reproducibility package. Upstream datasets and code remain subject to
their original terms.
