"""CLI entrypoint for ReleaseMindRepro."""

from __future__ import annotations

import argparse
import sys
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


def _normalize_argv(raw_args: list[str]) -> list[str]:
    """Return argv-style arguments with `--config` normalized before subcommands.

    This allows both:
      - `repro --config X cmd`
      - `repro cmd --config X`
    and keeps the repo docs/scripts usable even if users run the old style.
    """

    normalized: list[str] = []
    config_value: str | None = None
    skip_next = False

    for index, arg in enumerate(raw_args):
        if skip_next:
            skip_next = False
            continue

        if arg == "--config":
            if index + 1 >= len(raw_args):
                # Preserve parse failure for a clearer argparse message.
                normalized.append(arg)
                continue
            config_value = raw_args[index + 1]
            skip_next = True
            continue

        if arg.startswith("--config="):
            _, value = arg.split("=", 1)
            config_value = value
            continue

        normalized.append(arg)

    if config_value is None:
        return normalized

    return ["--config", config_value, *normalized]


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args(_normalize_argv(sys.argv[1:]))
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
