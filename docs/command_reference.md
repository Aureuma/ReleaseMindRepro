# 📘 Command Reference

All commands accept the global form `--config <path>` before command:

```bash
uv run releasemind-repro --config configs/paper.toml <command>
```

## 🩺 `doctor`

```bash
uv run releasemind-repro --config configs/paper.toml doctor [--require-audit-key] [--skip-neobert]
```

## 🧬 `train-proxies`

```bash
uv run releasemind-repro --config configs/paper.toml train-proxies [--smartnote ...]
```

Outputs: SmartNote proxy, RNSum proxy, model file, and proxy summary JSON.

## 🧪 `audit`

```bash
uv run releasemind-repro --config configs/paper.toml audit [--provider gemini|bedrock] [--sample-size N]
```

Outputs: `outputs/audit/oracle_audit.jsonl` plus optional raw JSONL and summary JSON.

## 📊 `evaluate-risk`

```bash
uv run releasemind-repro --config configs/paper.toml evaluate-risk [--deltas 0.1,0.2]
```

Outputs: `outputs/eval/risk_control_summary.csv` and `.meta.json`.

## 🗺️ `simulate-routing`

```bash
uv run releasemind-repro --config configs/paper.toml simulate-routing
```

Outputs: `outputs/routing/simulate_routing.csv` and per-dataset PDFs.

## 🛠️ `reproduce-paper`

```bash
uv run releasemind-repro --config configs/paper.toml reproduce-paper [--skip-*] [--continue-if-present]
```

Runs train → audit → evaluate → simulate.

## ✅ `verify`

```bash
uv run releasemind-repro --config configs/paper.toml verify --strict [--compare]
```

Checks required schema, optional manifest comparison, and returns a compact report.

## ⚖️ `compare`

```bash
uv run releasemind-repro --config configs/paper.toml compare --manifest artifacts/reference/manifest.json --strict --json
```

Compares generated files against expected reference artifacts.

## 🧾 `build-docs`

```bash
uv run releasemind-repro --config configs/paper.toml build-docs
```

Refreshes manifest + reproducibility metadata bundle.
