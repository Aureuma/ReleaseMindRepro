"""Command registry for the ReleaseMind reproducibility CLI."""

from __future__ import annotations

from typing import Callable, Dict, Tuple


def _import_command(path: str) -> Tuple[Callable, Callable]:
    module = __import__(path, fromlist=["add_parser", "run"])
    return getattr(module, "add_parser"), getattr(module, "run")


def command_registry() -> Dict[str, Tuple[Callable, Callable]]:
    return {
        "doctor": _import_command("releasemind_repro.commands.doctor"),
        "train-proxies": _import_command("releasemind_repro.commands.train_proxies"),
        "audit": _import_command("releasemind_repro.commands.audit"),
        "evaluate-risk": _import_command("releasemind_repro.commands.evaluate_risk"),
        "simulate-routing": _import_command("releasemind_repro.commands.simulate"),
        "reproduce-paper": _import_command("releasemind_repro.commands.reproduce"),
        "compare": _import_command("releasemind_repro.commands.compare"),
        "verify": _import_command("releasemind_repro.commands.verify"),
        "build-docs": _import_command("releasemind_repro.commands.build_docs"),
    }
