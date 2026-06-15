# ReleaseMindRepro

This repository is the public execution layer for reproducing the quantitative outputs from the ReleaseMind paper.

## Scope

- Recreate trained proxy artifacts and oracle-audit artifacts from public fixtures.
- Reproduce risk-control and routing outputs with deterministic defaults.
- Generate and verify reproducibility metadata (manifest, run metadata, docs).

## One-command summary

```bash
uv run releasemind-repro --config configs/paper_smoke.toml reproduce-paper
```

Use `paper_smoke.toml` for a fast smoke run and `paper.toml` for the full paper setup.

## Artifact mapping

```text
outputs/risk_proxy/*. -> proxy stage
outputs/audit/*.       -> oracle stage
outputs/eval/*.        -> risk-control stage
outputs/routing/*.     -> simulation stage
outputs/figures/*.     -> generated plots
artifacts/reference/*  -> reproducibility bundle
```

## Determinism notes

- Config merges are deterministic and CLI flags take precedence over TOML defaults.
- Steps are deterministic when inputs and seeds are fixed.
- Reference checks compare structured outputs first (`--strict` also checks hashes).
