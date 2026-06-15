"""Typed contracts and schema helpers for reproducibility artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd
import json


@dataclass(frozen=True)
class FileManifestRow:
    path: str
    sha256: str
    bytes: int
    rows: int | None = None


@dataclass(frozen=True)
class DatasetManifest:
    generated_with: str
    files: tuple[FileManifestRow, ...]


SMARTNOTE_PROXY_COLUMNS: tuple[str, ...] = ("body", "isInRN", "risk_score")
RNSUM_PROXY_COLUMNS: tuple[str, ...] = ("input_text", "target_text", "risk_score")
ORACLE_AUDIT_COLUMNS: tuple[str, ...] = (
    "audit_id",
    "dataset",
    "proxy_score",
    "oracle_label",
    "raw_output",
    "parsed_output",
)
RISK_SUMMARY_COLUMNS: tuple[str, ...] = (
    "dataset",
    "variant",
    "delta",
    "n_total",
    "n_accept",
    "coverage",
    "violations",
    "risk_rate",
    "risk_ci_low",
    "risk_ci_high",
    "oracle_calls",
)
ROUTING_COLUMNS: tuple[str, ...] = (
    "delta",
    "oracle_calls",
    "total",
    "cost",
    "avg_cost",
    "risk",
    "dataset",
    "proxy_model",
)


KEYS = {
    "smartnote_proxy": SMARTNOTE_PROXY_COLUMNS,
    "rnsum_proxy": RNSUM_PROXY_COLUMNS,
    "oracle_audit": ORACLE_AUDIT_COLUMNS,
    "risk_summary": RISK_SUMMARY_COLUMNS,
    "routing": ROUTING_COLUMNS,
}


def _to_dataframe(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix == ".parquet":
        return pd.read_parquet(path)
    raise ValueError(f"Unsupported tabular artifact extension: {suffix}")


def required_columns(dataset: str) -> tuple[str, ...]:
    try:
        return KEYS[dataset]
    except KeyError as exc:
        raise KeyError(f"Unknown dataset key: {dataset}") from exc


def check_columns(df: pd.DataFrame, required: Sequence[str]) -> tuple[bool, list[str]]:
    missing = [column for column in required if column not in df.columns]
    return not missing, missing


@dataclass(frozen=True)
class SchemaCheckResult:
    valid: bool
    errors: tuple[str, ...]


def validate_float_bounds(df: pd.DataFrame, columns: Iterable[str], lower: float, upper: float) -> SchemaCheckResult:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        return SchemaCheckResult(False, tuple(f"missing column: {column}" for column in missing))

    errors: list[str] = []
    for column in columns:
        values = pd.to_numeric(df[column], errors="coerce")
        invalid = ~((values.isna()) | ((values >= lower) & (values <= upper)))
        if bool(invalid.any()):
            errors.append(f"{column} has values outside [{lower}, {upper}]")

    return SchemaCheckResult(not errors, tuple(errors))


def validate_jsonl_rows(rows: Iterable[dict], required: Iterable[str]) -> SchemaCheckResult:
    required_set = set(required)
    missing_rows = []
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            missing_rows.append(f"row {idx}: not an object")
            continue
        row_keys = set(row.keys())
        missing = sorted(required_set - row_keys)
        if missing:
            missing_rows.append(f"row {idx}: missing {missing}")
    return SchemaCheckResult(not missing_rows, tuple(missing_rows))


def validate_artifact_rows(df: pd.DataFrame, required_columns: Sequence[str], *, strict: bool = False) -> SchemaCheckResult:
    if required_columns:
        missing = check_columns(df, required_columns)[1]
        if missing:
            return SchemaCheckResult(False, tuple(f"missing column {column}" for column in missing))
    if strict and df.empty:
        return SchemaCheckResult(False, ("artifact is empty",))
    return SchemaCheckResult(True, ())


def validate_artifact(path: Path, required_columns: Sequence[str], *, strict: bool = False) -> SchemaCheckResult:
    if not path.exists():
        return SchemaCheckResult(False, (f"missing file: {path}",))

    try:
        if path.suffix.lower() in {".csv", ".parquet"}:
            df = _to_dataframe(path)
            return validate_artifact_rows(df, required_columns, strict=strict)

        if path.suffix.lower() == ".jsonl":
            rows = []
            for line in path.read_text(encoding="utf-8").splitlines():
                text = line.strip()
                if not text:
                    continue
                rows.append(json.loads(text))

            if strict and not rows:
                return SchemaCheckResult(False, ("artifact is empty",))
            return validate_jsonl_rows(rows, required_columns)

        if path.suffix.lower() == ".json":
            payload = __import__("json").loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) and not isinstance(payload, list):
                return SchemaCheckResult(False, ("invalid json payload",))
            if strict and not payload:
                return SchemaCheckResult(False, ("artifact is empty",))
            return SchemaCheckResult(True, ())

        return SchemaCheckResult(True, ())
    except Exception as exc:
        return SchemaCheckResult(False, (f"validation failed: {exc}",))
