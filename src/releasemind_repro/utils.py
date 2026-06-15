"""General utilities used by reproducibility commands and adapters."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List

import numpy as np
import pandas as pd


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def read_jsonl(path: Path) -> Iterator[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            stripped = line.strip()
            if not stripped:
                continue
            yield json.loads(stripped)


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]], append: bool = False) -> None:
    ensure_dir(path.parent)
    mode = "a" if append else "w"
    with path.open(mode, encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_dataframe(path: Path, columns: List[str] | None = None) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")

    extension = path.suffix.lower()
    if extension in {".csv", ".tsv", ".txt"}:
        sep = "," if extension == ".csv" else "\t"
        return pd.read_csv(path, sep=sep, usecols=columns)  # type: ignore[arg-type]

    if extension in {".json", ".jsonl"}:
        if extension == ".jsonl":
            rows = list(read_jsonl(path))
            df = pd.DataFrame(rows)
        else:
            with path.open("r", encoding="utf-8") as stream:
                df = pd.DataFrame(json.load(stream))
        if columns:
            return df[[column for column in columns if column in df.columns]]
        return df

    if extension == ".parquet":
        return pd.read_parquet(path, columns=columns)

    return pd.read_parquet(path, columns=columns)


def checksum(path: Path) -> str:
    hash_ = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            hash_.update(chunk)
    return hash_.hexdigest()


def overlap_f1(a_tokens: List[str], b_tokens: List[str]) -> float:
    a_set = set(a_tokens)
    b_set = set(b_tokens)
    if not a_set or not b_set:
        return 0.0
    overlap = len(a_set.intersection(b_set))
    precision = overlap / max(1, len(a_set))
    recall = overlap / max(1, len(b_set))
    denom = precision + recall
    if denom <= 0:
        return 0.0
    return 2 * precision * recall / denom


def clopper_pearson(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    from scipy.stats import beta

    if n == 0:
        return float("nan"), float("nan")
    if k == 0:
        low = 0.0
    else:
        low = float(beta.ppf(alpha / 2, k, n - k + 1))
    if k == n:
        high = 1.0
    else:
        high = float(beta.ppf(1 - alpha / 2, k + 1, n - k))
    return low, high


def parse_bool(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def text_len_series(df: pd.Series) -> pd.Series:
    return df.fillna("").astype(str).str.len().astype(int)


def first_sentence(text: str) -> str:
    parts = [segment.strip() for segment in text.replace("\n", " ").replace("\r", " ").split(".")]
    for part in parts:
        if part:
            return part + "."
    return text.strip()


def truncate_chars(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    if max_chars <= 1:
        return text[: max(0, max_chars - 1)]
    return text[: max_chars - 1].rstrip() + "…"


def safe_ratio(numerator: float, denominator: float) -> float:
    return 0.0 if denominator <= 0 else float(numerator / denominator)


def normalize_flag(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "y", "yes", "on"}


def tokenized(text: str) -> List[str]:
    import re

    token_re = re.compile(r"[A-Za-z0-9_]+")
    return token_re.findall(str(text).lower())


# Backwards-compatible alias used by older modules.
def tokenize(text: str) -> List[str]:
    return tokenized(text)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def row_count(path: Path) -> int | None:
    if path.suffix.lower() == ".csv":
        try:
            return max(0, sum(1 for _ in path.open("r", encoding="utf-8")) - 1)
        except OSError:
            return None

    if path.suffix.lower() == ".jsonl":
        try:
            return sum(1 for _ in path.open("r", encoding="utf-8"))
        except OSError:
            return None

    if path.suffix.lower() == ".parquet":
        try:
            return len(pd.read_parquet(path))
        except Exception:
            return None

    if path.suffix.lower() in {".json", ".ndjson"}:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                return len(payload)
        except Exception:
            return None
    return None


def assert_in_range(series: pd.Series, lower: float, upper: float) -> bool:
    if series.empty:
        return True
    values = pd.to_numeric(series, errors="coerce")
    return bool(((values >= lower) & (values <= upper) | values.isna()).all())


def normalize_dataset_name(value: object) -> str:
    if not isinstance(value, str):
        return ""
    normalized = value.strip().lower()
    if normalized == "smartnote":
        return "smartnote"
    if normalized == "rnsum":
        return "rnsum"
    return normalized


def to_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def to_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def to_float_columns(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for column in cols:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    return df


def stable_json_load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_json_dump(obj: Any, path: Path) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")

