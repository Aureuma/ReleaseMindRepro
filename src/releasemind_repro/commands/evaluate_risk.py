"""Command handler for risk-control evaluation."""

from __future__ import annotations

from releasemind_repro.adapters.paper_eval import run as run_eval
from releasemind_repro.commands._helpers import merge_if_supplied, parse_comma_floats, print_json


def add_parser(subparsers, command: str) -> None:
    parser = subparsers.add_parser(command, help="Evaluate risk-control policy on oracle-labeled samples")
    parser.add_argument("--oracle", dest="oracle_out", default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--audit-frac", type=float, default=None)
    parser.add_argument("--deltas", default=None)
    parser.add_argument("--compare-corrections", action="store_true")
    parser.add_argument("--gap-quantile", type=float, default=None)
    parser.add_argument("--proxy-model", choices=["raw", "tfidf"], default=None)
    parser.add_argument("--out", dest="risk_eval_out", default=None)
    parser.add_argument("--meta-out", dest="risk_eval_meta_out", default=None)
    parser.add_argument("--figure-dir", dest="figure_dir", default=None)
    parser.add_argument("--mode", choices=["standard", "proxy_only", "tiered_oracle", "batch", "tiered_oracle"], default=None)
    parser.add_argument("--ci-alpha", type=float, default=None)
    parser.add_argument("--json", action="store_true")


def _normalize_mode(value: str | None) -> str:
    if value is None:
        return value
    normalized = value.replace("_", "_")
    if normalized == "proxy_only":
        return "standard"
    return normalized


def run(args, config) -> dict:
    updates = {
        "oracle_out": args.oracle_out,
        "seed": args.seed,
        "audit_frac": args.audit_frac,
        "deltas": parse_comma_floats(args.deltas),
        "compare_corrections": args.compare_corrections,
        "gap_quantile": args.gap_quantile,
        "proxy_model": args.proxy_model,
        "risk_eval_out": args.risk_eval_out,
        "risk_eval_meta_out": args.risk_eval_meta_out,
        "figure_dir": args.figure_dir,
        "ci_alpha": args.ci_alpha,
        "mode": _normalize_mode(args.mode),
    }
    cfg = merge_if_supplied(config, updates)
    report = run_eval(cfg)

    if args.json:
        print_json(report)
    else:
        print("Risk evaluation done")
        print(f"rows={report['rows']}")
        print(f"output={cfg.risk_eval_out}")
    return report
