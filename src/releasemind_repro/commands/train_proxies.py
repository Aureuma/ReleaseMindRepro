"""Command handler for proxy training."""

from __future__ import annotations

from pathlib import Path

from releasemind_repro.adapters import paper_train
from releasemind_repro.commands._helpers import merge_if_supplied, print_json


def add_parser(subparsers, command: str) -> None:
    parser = subparsers.add_parser(command, help="Train SmartNote and RNSum proxy models")
    parser.add_argument("--smartnote", dest="smartnote_dataset", default=None)
    parser.add_argument("--rnsum", dest="rnsum_dataset", default=None)
    parser.add_argument("--rnsum-proxy", dest="rnsum_proxy", default=None, choices=["overlap", "neobert"])
    parser.add_argument("--smartnote-tfidf-features", dest="tfidf_max_features", type=int, default=None)
    parser.add_argument("--n-jobs", dest="n_jobs", type=int, default=None)
    parser.add_argument("--out-dir", dest="out_dir", default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--json", action="store_true")


def _as_updates(cfg, args) -> dict[str, object]:
    updates: dict[str, object] = {
        "smartnote_dataset": args.smartnote_dataset,
        "rnsum_dataset": args.rnsum_dataset,
        "rnsum_proxy": args.rnsum_proxy,
        "tfidf_max_features": args.tfidf_max_features,
        "n_jobs": args.n_jobs,
        "seed": args.seed,
        "overwrite": bool(args.overwrite),
    }
    if args.out_dir:
        output = Path(args.out_dir)
        updates.update(
            {
                "smartnote_proxy_out": str(output / "smartnote_proxy.parquet"),
                "rnsum_proxy_out": str(output / "rnsum_proxy.parquet"),
                "smartnote_tfidf_model_out": str(output / "smartnote_tfidf_logreg.joblib"),
                "proxy_summary_out": str(output / "proxy_summary.json"),
            }
        )
    return updates


def run_cmd(args, config) -> dict:
    cfg = merge_if_supplied(config, _as_updates(config, args))

    report = paper_train.run(cfg)
    if args.json:
        print_json(report)
    else:
        print("Training done")
        print(f"smartnote_proxy={cfg.smartnote_proxy_out}")
        print(f"rnsum_proxy={cfg.rnsum_proxy_out}")
    return report


run = run_cmd
