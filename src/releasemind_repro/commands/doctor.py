"""Validate environment, dependencies, and configuration."""

from __future__ import annotations

import importlib
import os
from pathlib import Path

from releasemind_repro.config import load_config
from releasemind_repro.commands._helpers import print_json


def add_parser(subparsers, command: str) -> None:
    parser = subparsers.add_parser(command, help="Check environment and configuration")
    parser.add_argument("--require-audit-key", action="store_true")
    parser.add_argument("--skip-neobert", action="store_true")
    parser.add_argument("--json", action="store_true")


def _dependency_available(module_name: str) -> bool:
    try:
        importlib.import_module(module_name)
        return True
    except Exception:
        return False


def run(args, config=None) -> None:
    cfg = load_config(Path(getattr(args, "config", "configs/paper.toml")))

    report = {
        "config_path": str(args.config),
        "config_fingerprint": cfg.fingerprint(),
        "path_checks": cfg.validate(),
        "dependencies": {},
        "provider_keys": {},
    }

    core_modules = [
        "pandas",
        "numpy",
        "sklearn",
        "scipy",
        "matplotlib",
        "joblib",
        "pyarrow",
    ]
    optional_oracle = ["google.genai", "boto3"]
    neobert_modules = ["torch", "transformers", "tokenizers", "safetensors"]

    for module in core_modules:
        report["dependencies"][module] = _dependency_available(module)
    for module in optional_oracle:
        report["dependencies"][module] = _dependency_available(module)

    if not args.skip_neobert:
        for module in neobert_modules:
            report["dependencies"][module] = _dependency_available(module)

    report["provider_keys"] = {
        "GOOGLE_API_KEY": bool(os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")),
        "AWS_ACCESS_KEY_ID": bool(os.environ.get("AWS_ACCESS_KEY_ID")),
        "AWS_SECRET_ACCESS_KEY": bool(os.environ.get("AWS_SECRET_ACCESS_KEY")),
        "AWS_DEFAULT_REGION": bool(os.environ.get("AWS_DEFAULT_REGION")),
    }

    if args.require_audit_key and not (report["provider_keys"]["GOOGLE_API_KEY"] or (
        report["provider_keys"]["AWS_ACCESS_KEY_ID"] and report["provider_keys"]["AWS_SECRET_ACCESS_KEY"] and report["provider_keys"]["AWS_DEFAULT_REGION"]
    )):
        report["ok"] = False
        report["provider_keys"]["required"] = "Set Google or AWS Bedrock credentials"
    else:
        report["ok"] = True

    if args.json:
        print_json(report)
        return

    print(f"config: {args.config}")
    print(f"fingerprint: {cfg.fingerprint()}")
    for group, ok in report["dependencies"].items():
        print(f"  {'ok' if ok else 'missing'}: {group}")
    if report["path_checks"]:
        print("warnings:")
        for warning in report["path_checks"]:
            print(f" - {warning}")
