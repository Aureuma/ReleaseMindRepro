"""Command handler for oracle-audit execution."""

from __future__ import annotations

from releasemind_repro.adapters.paper_oracle import run as run_oracle
from releasemind_repro.commands._helpers import merge_if_supplied, print_json


def add_parser(subparsers, command: str) -> None:
    parser = subparsers.add_parser(command, help="Run LLM oracle audit on sampled proxy rows")
    parser.add_argument("--smartnote-proxy", dest="smartnote_proxy", default=None)
    parser.add_argument("--rnsum-proxy", dest="rnsum_proxy", default=None)
    parser.add_argument("--out", dest="oracle_out", default=None)
    parser.add_argument("--summary", dest="oracle_summary_out", default=None)
    parser.add_argument("--raw", dest="oracle_raw_out", default=None)
    parser.add_argument("--sample-size", dest="sample_size", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--provider", choices=["gemini", "bedrock"], default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--mode", choices=["standard", "batch", "tiered_oracle"], default=None)
    parser.add_argument("--batch-dir", default=None)
    parser.add_argument("--batch-poll-interval", type=int, default=None)
    parser.add_argument("--max-workers", type=int, default=None)
    parser.add_argument("--max-retries", type=int, default=None)
    parser.add_argument("--min-delay", type=float, default=None)
    parser.add_argument("--min-interval", type=float, default=None)
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--max-tokens", type=int, default=None)
    parser.add_argument("--skip-if-missing", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--overwrite", action="store_true")


def _as_updates(args) -> dict[str, object]:
    return {
        "smartnote_proxy_out": args.smartnote_proxy,
        "rnsum_proxy_out": args.rnsum_proxy,
        "oracle_out": args.oracle_out,
        "oracle_summary_out": args.oracle_summary_out,
        "oracle_raw_out": args.oracle_raw_out,
        "sample_size": args.sample_size,
        "seed": args.seed,
        "provider": args.provider,
        "model": args.model,
        "oracle_mode": args.mode,
        "audit_provider": args.provider,
        "audit_mode": args.mode,
        "oracle_batch_dir": args.batch_dir,
        "batch_poll_interval": args.batch_poll_interval,
        "max_workers": args.max_workers,
        "max_retries": args.max_retries,
        "min_delay": args.min_delay,
        "min_interval": args.min_interval,
        "temperature": args.temperature,
        "max_tokens": args.max_tokens,
        "overwrite": bool(args.overwrite),
        "skip_if_missing": bool(args.skip_if_missing),
    }


def run(args, config) -> dict:
    cfg = merge_if_supplied(config, _as_updates(args))

    report = run_oracle(
        cfg,
        sample_size_override=args.sample_size,
        mode_override=args.mode,
        provider_override=args.provider,
        model_override=args.model,
        skip_if_missing=args.skip_if_missing,
    )

    if args.json:
        print_json(report)
    else:
        print("Audit done")
        print(f"rows={report.get('rows')}")
        print(f"output={cfg.oracle_out}")
        if getattr(args, "raw", False):
            print(f"raw_output={cfg.oracle_raw_out}")
    return report
