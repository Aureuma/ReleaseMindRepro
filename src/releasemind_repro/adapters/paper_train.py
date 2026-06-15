"""Adapter layer mapping CLI config into proxy training implementation."""

from __future__ import annotations

import json
from pathlib import Path

from releasemind_repro import proxy


def run(cfg) -> dict[str, object]:
    result = proxy.train_and_summary(
        smartnote_source=cfg.smartnote_dataset,
        rnsum_source=cfg.rnsum_dataset,
        out_dir=cfg.smartnote_proxy_out.parent,
        max_features=cfg.tfidf_max_features,
        n_jobs=cfg.n_jobs,
        rnsum_proxy=cfg.rnsum_proxy_mode,
        neobert_model=cfg.neobert_model,
        neobert_batch_size=cfg.neobert_batch_size,
        neobert_max_length=cfg.neobert_max_length,
        neobert_threads=cfg.neobert_threads,
        trust_remote_code=cfg.trust_remote_code,
    )

    summary = {
        "generated_with": "train-proxies",
        "smartnote": result["smartnote"],
        "rnsum": result["rnsum"],
        "rnsum_proxy": result["rnsum_proxy"],
        "max_features": cfg.tfidf_max_features,
        "n_jobs": cfg.n_jobs,
    }
    cfg.proxy_summary_out.parent.mkdir(parents=True, exist_ok=True)
    cfg.proxy_summary_out.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    return {
        "output": {
            "smartnote_proxy": str(cfg.smartnote_proxy_out),
            "rnsum_proxy": str(cfg.rnsum_proxy_out),
        },
        "summary": summary,
    }
