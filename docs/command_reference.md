# Command Reference

## Global

All commands accept `--config <path>` and `--json` where documented.

## `doctor`

```bash
uv run releasemind-repro doctor --config configs/paper.toml [--require-audit-key] [--skip-neobert]
```

## `train-proxies`

```bash
uv run releasemind-repro train-proxies --config configs/paper.toml [--smartnote ...]
```

Outputs: SmartNote proxy, RNSum proxy, model file, proxy summary JSON.

## `audit`

```bash
uv run releasemind-repro audit --config configs/paper.toml [--provider gemini|bedrock] [--sample-size N]
```

Outputs: oracle audit JSONL, optional raw JSONL, oracle summary JSON.

## `evaluate-risk`

```bash
uv run releasemind-repro evaluate-risk --config configs/paper.toml [--deltas 0.1,0.2]
```

Outputs: `outputs/eval/risk_control_summary.csv` and `.meta.json`, plus per-dataset curves.

## `simulate-routing`

```bash
uv run releasemind-repro simulate-routing --config configs/paper.toml
```

Outputs: `outputs/routing/simulate_routing.csv` and per-dataset routing PDFs.

## `reproduce-paper`

```bash
uv run releasemind-repro reproduce-paper --config configs/paper.toml [--skip-*] [--continue-if-present]
```

Runs train → audit → evaluate → simulate.

## `verify`

```bash
uv run releasemind-repro verify --config configs/paper.toml --strict [--compare]
```

Checks schema/required columns and optionally compares against manifest.

## `compare`

```bash
uv run releasemind-repro compare --config configs/paper.toml --manifest artifacts/reference/manifest.json --strict --json
```

Compares generated files against reference artifacts.

## `build-docs`

```bash
uv run releasemind-repro build-docs --config configs/paper.toml
```

Refreshes manifest and run metadata.
