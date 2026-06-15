"""Shared utilities for command implementations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from releasemind_repro.config import ReproConfig


def make_step_result(status: str, **fields: object) -> dict[str, object]:
    payload: dict[str, object] = {"status": status}
    payload.update(fields)
    return payload


def is_nonempty_file(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


def print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))


def merge_if_supplied(config: ReproConfig, updates: dict[str, Any]) -> ReproConfig:
    payload = {key: value for key, value in updates.items() if value is not None}
    return config if not payload else config.merge(payload)


def to_path_arg(value: str | None) -> str | None:
    return value


def to_int_arg(value: int | None) -> int | None:
    return value


def to_float_arg(value: float | None) -> float | None:
    return value


def parse_comma_floats(value: str | None) -> list[float] | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    values: list[float] = []
    for item in text.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            values.append(float(item))
        except ValueError:
            continue
    return values


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_lines(lines: list[str], path: Path) -> None:
    ensure_parent(path)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def sha256_of_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()
