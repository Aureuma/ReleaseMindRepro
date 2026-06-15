# Architecture

```mermaid
flowchart TD
  A[smartnote dataset] --> B[train-proxies]
  C[rnsum dataset] --> B
  B --> D[oracle audit]
  D --> E[evaluate-risk]
  E --> F[simulate-routing]
  B --> F
  D --> G[outputs]
  E --> G
  F --> G
  G --> H[build-docs / verify / compare]
```

## Stage contracts

- `train-proxies` creates model and score columns for both datasets.
- `audit` labels sampled rows with an LLM-oracle policy.
- `evaluate-risk` computes risk/cost acceptance metrics and CI bands.
- `simulate-routing` simulates threshold behavior and oracle usage.
- `build-docs` materializes reference manifest and reproducibility metadata.
