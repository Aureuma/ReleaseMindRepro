"""Compare generated artifacts against a reference manifest."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from releasemind_repro.commands._helpers import print_json
from releasemind_repro.pipeline.reference import FileLookupError, ReferenceManifest, file_lookup, load_manifest


def add_parser(subparsers, command: str) -> None:
    parser = subparsers.add_parser(command, help="Compare outputs against reference manifest")
    parser.add_argument("--reference-dir", default=None)
    parser.add_argument("--manifest", default="artifacts/reference/manifest.json")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--tolerance", type=float, default=0.0)
    parser.add_argument("--json", action="store_true")


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize_string(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_rows(obj: Any) -> Any:
    if isinstance(obj, dict):
        out = {}
        for key in sorted(obj.keys()):
            out[key] = _normalize_rows(obj[key])
        return out
    if isinstance(obj, list):
        return [_normalize_rows(item) for item in obj]
    if isinstance(obj, str):
        return _normalize_string(obj)
    return obj


def _compare_numbers(left: Any, right: Any, tolerance: float) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return left == right

    try:
        left_value = float(left)
        right_value = float(right)
    except (TypeError, ValueError):
        return False

    if pd.isna(left_value) and pd.isna(right_value):
        return True
    if pd.isna(left_value) or pd.isna(right_value):
        return False

    return abs(left_value - right_value) <= tolerance


def _compare_items(left: Any, right: Any, tolerance: float) -> bool:
    if type(left) != type(right):
        # allow numeric cross-type comparisons
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            return _compare_numbers(left, right, tolerance)
        return False

    if isinstance(left, dict):
        if set(left.keys()) != set(right.keys()):
            return False
        return all(_compare_items(left[key], right[key], tolerance) for key in left)

    if isinstance(left, list):
        if len(left) != len(right):
            return False
        return all(_compare_items(a, b, tolerance) for a, b in zip(left, right))

    if isinstance(left, (int, float)) and not isinstance(left, bool):
        return _compare_numbers(left, right, tolerance)

    if isinstance(left, str):
        return _normalize_string(left) == _normalize_string(right)

    return left == right


def _compare_json(path_left: Path, path_right: Path, tolerance: float) -> tuple[bool, str]:
    with path_left.open("r", encoding="utf-8") as left_file:
        left_value = json.load(left_file)
    with path_right.open("r", encoding="utf-8") as right_file:
        right_value = json.load(right_file)

    left_norm = _normalize_rows(left_value)
    right_norm = _normalize_rows(right_value)
    if _compare_items(left_norm, right_norm, tolerance):
        return True, "ok"
    return False, "json mismatch"


def _read_jsonl(path: Path) -> list[Any]:
    rows: list[Any] = []
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            text = line.strip()
            if not text:
                continue
            rows.append(json.loads(text))
    return rows


def _compare_jsonl(path_left: Path, path_right: Path, tolerance: float) -> tuple[bool, str]:
    left_rows = _read_jsonl(path_left)
    right_rows = _read_jsonl(path_right)

    if len(left_rows) != len(right_rows):
        return False, "row count differ"

    for left, right in zip(left_rows, right_rows):
        if not _compare_items(_normalize_rows(left), _normalize_rows(right), tolerance):
            return False, "jsonl mismatch"
    return True, "ok"


def _compare_df(actual: pd.DataFrame, reference: pd.DataFrame, tolerance: float) -> tuple[bool, str]:
    if list(actual.columns) != list(reference.columns):
        return False, "columns differ"
    if len(actual) != len(reference):
        return False, "row count differ"

    for column in actual.columns:
        if pd.api.types.is_float_dtype(actual[column]) or pd.api.types.is_integer_dtype(actual[column]):
            left = pd.to_numeric(actual[column], errors="coerce")
            right = pd.to_numeric(reference[column], errors="coerce")
            diff = (left - right).abs()
            if any(diff.fillna(pd.Series([float("inf")] * len(diff))) > tolerance):
                return False, f"field {column} mismatch"
        else:
            if not all(_compare_items(a, b, tolerance) for a, b in zip(actual[column], reference[column])):
                return False, f"field {column} mismatch"
    return True, "ok"


def _compare_parquet(path_left: Path, path_right: Path, tolerance: float) -> tuple[bool, str]:
    return _compare_df(pd.read_parquet(path_left), pd.read_parquet(path_right), tolerance)


def _compare_csv(path_left: Path, path_right: Path, tolerance: float) -> tuple[bool, str]:
    return _compare_df(pd.read_csv(path_left), pd.read_csv(path_right), tolerance)


def _row_count(path: Path, ext: str) -> int | None:
    try:
        if ext == ".json":
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                return len(payload)
            return 1
        if ext == ".jsonl":
            return len(_read_jsonl(path))
        if ext == ".csv":
            return len(pd.read_csv(path))
        if ext == ".parquet":
            return len(pd.read_parquet(path))
    except Exception:
        return None
    return None


def run(args, config) -> dict[str, Any]:
    reference_root = Path(args.reference_dir) if args.reference_dir else config.reference_dir
    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = Path(config.root) / manifest_path

    if not manifest_path.exists():
        report = {
            "ok": False,
            "results": [
                {
                    "path": str(manifest_path),
                    "status": False,
                    "detail": "missing manifest",
                }
            ],
        }
        if args.json:
            print_json(report)
        return report

    manifest = load_manifest(manifest_path)
    reference_files = file_lookup(manifest)
    if not manifest.files:
        report = {"ok": False, "results": [{"path": "manifest", "status": False, "detail": "manifest is empty"}]}
        if args.json:
            print_json(report)
        return report

    results: list[dict[str, object]] = []
    all_ok = True

    for path, reference_row in reference_files.items():
        actual_path = config.root / path
        expected_path = reference_root / path

        if not expected_path.exists():
            details = "reference file missing"
            results.append({"path": path, "status": False, "detail": details})
            all_ok = False
            continue

        if not actual_path.exists():
            details = "actual path missing"
            results.append({"path": path, "status": False, "detail": details})
            all_ok = False
            continue

        if args.strict:
            actual_hash = _hash_file(actual_path)
            if reference_row.sha256 and actual_hash != reference_row.sha256:
                results.append({"path": path, "status": False, "detail": "hash mismatch"})
                all_ok = False
                continue

            expected_rows = reference_row.rows
            actual_rows = _row_count(actual_path, actual_path.suffix.lower())
            if expected_rows is not None and actual_rows is not None and expected_rows != actual_rows:
                results.append({"path": path, "status": False, "detail": "row count mismatch"})
                all_ok = False
                continue

            if expected_path.stat().st_size == 0 and actual_path.stat().st_size != 0:
                results.append({"path": path, "status": False, "detail": "empty mismatch"})
                all_ok = False
                continue

        ext = actual_path.suffix.lower()
        if ext == ".csv":
            status, detail = _compare_csv(actual_path, expected_path, args.tolerance)
        elif ext == ".jsonl":
            status, detail = _compare_jsonl(actual_path, expected_path, args.tolerance)
        elif ext == ".json":
            status, detail = _compare_json(actual_path, expected_path, args.tolerance)
        elif ext == ".parquet":
            status, detail = _compare_parquet(actual_path, expected_path, args.tolerance)
        else:
            status = actual_path.stat().st_size == expected_path.stat().st_size
            detail = "ok" if status else "binary size mismatch"

        results.append({"path": path, "status": bool(status), "detail": detail})
        all_ok = all_ok and bool(status)

    report = {"ok": all_ok, "results": results}
    if args.json:
        print_json(report)
    return report
