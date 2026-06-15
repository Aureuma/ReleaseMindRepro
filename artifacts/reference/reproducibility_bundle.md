# ReleaseMindRepro Reproducibility Bundle

This folder stores deterministic reference metadata for reproducibility checks.

## Included references

- `manifest.json`: list of expected artifacts and checksums.
- `run-meta.json`: command metadata and run fingerprint used to populate manifest.

## Refresh workflow

Run:

```bash
python scripts/build_reference_bundle.py --config configs/paper_smoke.toml
```

or

```bash
releasemind-repro build-docs --config configs/paper_smoke.toml
```

Then compare current outputs with:

```bash
releasemind-repro compare --config configs/paper_smoke.toml --strict
```

If you prefer the provided scripts:

```bash
./scripts/repro_smoke.sh
./scripts/repro_paper.sh
./scripts/compare_reference.sh
```
