# Dataset Setup

## Public data used by paper

- SmartNote: upstream SmartNote dataset (or curated fixtures).
- RNSum: upstream RNSum release (or curated fixtures).

## Repository defaults

Default fixture paths are under `data/fixtures/`.

- `data/fixtures/smartnote_small.parquet`
- `data/fixtures/rnsum_small.jsonl`

## Full data workflow

1. Download upstream datasets using upstream licenses.
2. Place data files under `data/raw/` (or override paths in the config).
3. Point `configs/paper.toml` to the desired source files.
4. Re-run `train-proxies`.
