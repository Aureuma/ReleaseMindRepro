# Artifact Manifest Contract

## Required columns

- `risk_proxy/smartnote_proxy.parquet`
  - `body`, `isInRN`, `risk_score`
- `risk_proxy/rnsum_proxy.parquet`
  - `input_text`, `target_text`, `risk_score`
- `audit/oracle_audit.jsonl`
  - `audit_id`, `dataset`, `proxy_score`, `oracle_label`, `raw_output`, `parsed_output`
- `eval/risk_control_summary.csv`
  - `dataset`, `variant`, `delta`, `n_total`, `n_accept`, `coverage`, `violations`, `risk_rate`, `risk_ci_low`, `risk_ci_high`, `oracle_calls`
- `routing/simulate_routing.csv`
  - `delta`, `oracle_calls`, `total`, `cost`, `avg_cost`, `risk`, `dataset`, `proxy_model`

## Verification strategy

- `verify --strict` checks required column presence and non-empty mode when enabled.
- `compare --strict` checks row counts and checksums when manifest paths exist.
