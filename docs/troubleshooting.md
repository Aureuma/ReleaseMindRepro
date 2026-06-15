# Troubleshooting

## Common failures

- Missing dataset paths
  - Check `smartnote_dataset` and `rnsum_dataset` in config.
  - Run `doctor` to print active config fingerprint and path warnings.

- LLM credential errors
  - Set `GOOGLE_API_KEY` for Gemini or `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION` for Bedrock.

- Parse/labeling mismatches
  - Re-run `audit --skip-if-missing` to generate deterministic empty outputs when credentials are intentionally unavailable.

- Compare hash mismatch
  - Confirm command/path parity and `--strict` mode assumptions.
  - Rebuild manifest with `build-docs` after expected updates.
