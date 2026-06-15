"""Adapter layer for audit operations."""

from __future__ import annotations

from typing import Dict

from releasemind_repro import oracle


def run(
    cfg,
    sample_size_override: int | None = None,
    mode_override: str | None = None,
    provider_override: str | None = None,
    model_override: str | None = None,
    skip_if_missing: bool = False,
) -> Dict[str, object]:
    sample_size = int(sample_size_override if sample_size_override is not None else cfg.sample_size)
    mode = mode_override or cfg.oracle_mode

    return oracle.run_audit(
        smartnote_proxy=cfg.smartnote_proxy_out,
        rnsum_proxy=cfg.rnsum_proxy_out,
        out=cfg.oracle_out,
        summary_out=cfg.oracle_summary_out,
        sample_size=sample_size,
        seed=cfg.seed,
        provider=(provider_override or cfg.provider),
        model=(model_override or cfg.model),
        mode=mode,
        batch_dir=cfg.oracle_batch_dir,
        batch_poll_interval=cfg.batch_poll_interval,
        max_workers=cfg.max_workers,
        max_retries=cfg.max_retries,
        min_delay=cfg.min_delay,
        min_interval=cfg.min_interval,
        temperature=cfg.temperature,
        max_tokens=cfg.max_tokens,
        bins=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
        overwrite=cfg.overwrite,
        raw_out=cfg.oracle_raw_out,
        skip_if_missing=skip_if_missing,
    )
