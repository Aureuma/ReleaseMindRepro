"""Command handler for routing simulation."""

from __future__ import annotations

from releasemind_repro.adapters.paper_simulate import run as run_simulate
from releasemind_repro.commands._helpers import merge_if_supplied, print_json


def add_parser(subparsers, command: str) -> None:
    parser = subparsers.add_parser(command, help="Simulate routing cost-risk trade-offs")
    parser.add_argument("--oracle", dest="oracle_out", default=None)
    parser.add_argument("--proxy-cost", type=float, default=None)
    parser.add_argument("--oracle-cost", type=float, default=None)
    parser.add_argument("--delta-step", type=float, default=None)
    parser.add_argument("--proxy-model", dest="proxy_model", choices=["raw", "tfidf"], default=None)
    parser.add_argument("--out", dest="routing_out", default=None)
    parser.add_argument("--figure-dir", dest="figure_dir", default=None)
    parser.add_argument("--json", action="store_true")


def run(args, config) -> dict:
    cfg = merge_if_supplied(
        config,
        {
            "oracle_out": args.oracle_out,
            "proxy_cost": args.proxy_cost,
            "oracle_cost": args.oracle_cost,
            "delta_step": args.delta_step,
            "proxy_model": args.proxy_model,
            "routing_out": args.routing_out,
            "figure_dir": args.figure_dir,
        },
    )

    report = run_simulate(cfg)
    if args.json:
        print_json(report)
    else:
        print("Simulation done")
        print(f"rows={report['rows']}")
        print(f"output={cfg.routing_out}")
    return report
