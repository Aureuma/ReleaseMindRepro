"""CLI entrypoint for ReleaseMindRepro."""

from __future__ import annotations

import argparse
from pathlib import Path

from importlib.metadata import PackageNotFoundError

from releasemind_repro.commands import command_registry
from releasemind_repro.config import load_config


def _package_version() -> str:
    try:
        from importlib.metadata import version

        return version("releasemind-repro")
    except (PackageNotFoundError, Exception):  # pragma: no cover
        return "0.0.0"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ReleaseMind reproducibility CLI")
    parser.add_argument("--config", default="configs/paper.toml", help="Path to TOML config")
    parser.add_argument("--version", action="version", version=f"%(prog)s {_package_version()}")

    subparsers = parser.add_subparsers(dest="command", required=True)

    for name, (add_parser, _run) in command_registry().items():
        add_parser(subparsers, command=name)

    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    registry = command_registry()

    config_path = Path(args.config)

    if args.command == "doctor":
        _, run = registry[args.command]
        run(args)
        return 0

    if args.command == "build-docs":
        config = load_config(config_path)
        _, run = registry[args.command]
        run(args, config)
        return 0

    if args.command not in registry:
        parser.error(f"Unknown command: {args.command}")
        return 2

    config = load_config(config_path)
    _, run = registry[args.command]
    run(args, config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
