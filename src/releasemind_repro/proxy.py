"""Proxy training and scoring for ReleaseMind reproducibility experiments."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from .utils import overlap_f1, read_dataframe, tokenized


def build_rnsum_text(row: Dict) -> tuple[str, str]:
    commit_messages = row.get("commit_messages")
    if isinstance(commit_messages, list):
        input_text = "\n".join(str(msg).strip() for msg in commit_messages if msg)
    elif isinstance(commit_messages, str):
        input_text = commit_messages.strip()
    else:
        input_text = ""

    release_note = row.get("release_note")
    target_text = ""
    if isinstance(release_note, dict):
        parts = []
        for category, items in release_note.items():
            if not items:
                continue
            if isinstance(items, list):
                text = "; ".join(str(item).strip() for item in items if item)
            else:
                text = str(items).strip()
            if text:
                parts.append(f"{category}: {text}")
        target_text = " ".join(parts)
    elif isinstance(release_note, list):
        target_text = "; ".join(str(item).strip() for item in release_note if item)
    elif isinstance(release_note, str):
        target_text = release_note.strip()

    return input_text, target_text


def _encode_texts_neobert(texts: List[str], tokenizer, model, batch_size: int, max_length: int, device):
    import torch
    import torch.nn.functional as F

    vectors: list[torch.Tensor] = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        encoded = tokenizer(
            batch,
            padding=True,
            truncation=True,
            max_length=max_length,
            return_tensors="pt",
        )
        attention_mask = encoded.get("attention_mask")
        if attention_mask is None:
            pool_mask = torch.ones_like(encoded["input_ids"], dtype=torch.float)
        else:
            # Paper parity: invert for SDPA-compatible mean pooling behaviour.
            pool_mask = attention_mask.unsqueeze(-1).to(dtype=torch.float)
            encoded["attention_mask"] = (attention_mask == 0)

        encoded = {key: value.to(device) for key, value in encoded.items()}
        pool_mask = pool_mask.to(device)

        with torch.inference_mode():
            outputs = model(**encoded)
            last_hidden_state = outputs.last_hidden_state
            summed = (last_hidden_state * pool_mask).sum(dim=1)
            denom = pool_mask.sum(dim=1).clamp(min=1e-9)
            pooled = summed / denom
            pooled = F.normalize(pooled, p=2, dim=1)
            vectors.append(pooled.cpu())

    if not vectors:
        return torch.empty((0, 1), dtype=torch.float32)
    return torch.cat(vectors, dim=0)


def _ensure_xformers_ops() -> None:
    try:
        import xformers.ops  # noqa: F401
        return
    except Exception:
        import sys
        import types
        from torch import nn

        class SwiGLU(nn.Module):
            def __init__(self, in_features: int, hidden_features: int, out_features: int, bias: bool = True) -> None:
                super().__init__()
                self.w12 = nn.Linear(in_features, hidden_features * 2, bias=bias)
                self.w3 = nn.Linear(hidden_features, out_features, bias=bias)
                self.act = nn.SiLU()

            def forward(self, x):
                x12 = self.w12(x)
                x1, x2 = x12.chunk(2, dim=-1)
                return self.w3(self.act(x1) * x2)

        ops_mod = types.ModuleType("xformers.ops")
        ops_mod.SwiGLU = SwiGLU
        xf_mod = types.ModuleType("xformers")
        xf_mod.ops = ops_mod
        sys.modules.setdefault("xformers", xf_mod)
        sys.modules["xformers.ops"] = ops_mod


def run_rnsum_overlap_proxy(source: Path, out_dir: Path) -> Dict[str, int | str]:
    rows: list[dict[str, object]] = []
    total = 0
    kept = 0

    with source.open("r", encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            total += 1
            item = json.loads(line)
            input_text, target_text = build_rnsum_text(item)
            if not input_text or not target_text:
                continue
            kept += 1
            risk_score = 1.0 - overlap_f1(tokenized(input_text), tokenized(target_text))
            rows.append({
                "input_text": input_text,
                "target_text": target_text,
                "risk_score": float(risk_score),
            })

    if not rows:
        raise ValueError(f"No usable rows in RNSum source: {source}")

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "rnsum_proxy.parquet"
    pd.DataFrame(rows).to_parquet(out_path, index=False)
    return {
        "total": total,
        "kept": kept,
        "out": str(out_path),
        "proxy": "overlap",
    }


def run_rnsum_neobert_proxy(
    source: Path,
    out_dir: Path,
    model_name: str,
    batch_size: int,
    max_length: int,
    num_threads: Optional[int],
    trust_remote_code: bool,
) -> Dict[str, int | str]:
    rows: list[dict[str, object]] = []
    total = 0
    kept = 0

    with source.open("r", encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            total += 1
            item = json.loads(line)
            input_text, target_text = build_rnsum_text(item)
            if not input_text or not target_text:
                continue
            kept += 1
            rows.append({
                "input_text": input_text,
                "target_text": target_text,
            })

    if not rows:
        raise ValueError(f"No usable rows in RNSum source: {source}")

    try:
        import torch
        from transformers import AutoModel, AutoTokenizer
    except Exception as exc:
        raise ImportError("torch and transformers are required for NeoBERT proxy mode") from exc

    _ensure_xformers_ops()
    if num_threads is not None:
        torch.set_num_threads(num_threads)

    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=trust_remote_code)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token if tokenizer.eos_token is not None else tokenizer.unk_token

    model = AutoModel.from_pretrained(model_name, trust_remote_code=trust_remote_code)
    model.eval()
    model = model.to("cpu")

    input_texts = [row["input_text"] for row in rows]
    target_texts = [row["target_text"] for row in rows]
    input_vecs = _encode_texts_neobert(
        input_texts,
        tokenizer,
        model,
        batch_size=batch_size,
        max_length=max_length,
        device="cpu",
    )
    target_vecs = _encode_texts_neobert(
        target_texts,
        tokenizer,
        model,
        batch_size=batch_size,
        max_length=max_length,
        device="cpu",
    )

    similarities = (input_vecs * target_vecs).sum(dim=1).clamp(min=-1.0, max=1.0).tolist() if len(input_vecs) else []
    for row, sim in zip(rows, similarities, strict=False):
        sim_value = float(sim)
        row["similarity"] = sim_value
        row["risk_score"] = float((1.0 - sim_value))

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "rnsum_proxy.parquet"
    pd.DataFrame(rows).to_parquet(out_path, index=False)

    return {
        "total": total,
        "kept": kept,
        "out": str(out_path),
        "proxy": "neobert",
    }


def train_smartnote_proxy(
    source: Path,
    out_dir: Path,
    max_features: int,
    n_jobs: int,
    max_iter: int = 1000,
) -> Dict[str, str]:
    df = read_dataframe(source, columns=["body", "isInRN"])
    if df.empty:
        raise ValueError(f"SmartNote dataset is empty: {source}")

    df = df.dropna(subset=["body", "isInRN"]).copy()
    df["body"] = df["body"].astype(str).str.strip()
    df = df[df["body"] != ""].copy()
    if df.empty:
        raise ValueError(f"No usable SmartNote rows in {source}")

    model = Pipeline([
        ("tfidf", TfidfVectorizer(max_features=max_features, stop_words="english")),
        ("clf", LogisticRegression(max_iter=max_iter, n_jobs=n_jobs, class_weight="balanced")),
    ])
    model.fit(df["body"], df["isInRN"].astype(int))
    risk_score = model.predict_proba(df["body"])[:, 1]

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "smartnote_proxy.parquet"
    model_path = out_dir / "smartnote_tfidf_logreg.joblib"

    out_df = pd.DataFrame({
        "body": df["body"].astype(str),
        "isInRN": df["isInRN"].astype(bool),
        "risk_score": risk_score.astype(float),
    })
    out_df.to_parquet(out_path, index=False)
    joblib.dump(model, model_path)

    return {
        "rows": str(len(out_df)),
        "out": str(out_path),
        "model": str(model_path),
        "classes": len(model.named_steps["clf"].classes_),
    }


def train_and_summary(
    smartnote_source: Path,
    rnsum_source: Path,
    out_dir: Path,
    max_features: int,
    n_jobs: int,
    rnsum_proxy: str,
    neobert_model: str,
    neobert_batch_size: int,
    neobert_max_length: int,
    neobert_threads: int,
    trust_remote_code: bool,
) -> Dict[str, object]:
    out_dir = Path(out_dir)
    smartnote_result = train_smartnote_proxy(
        source=smartnote_source,
        out_dir=out_dir,
        max_features=max_features,
        n_jobs=n_jobs,
    )

    if rnsum_proxy == "neobert":
        rnsum_result = run_rnsum_neobert_proxy(
            source=rnsum_source,
            out_dir=out_dir,
            model_name=neobert_model,
            batch_size=neobert_batch_size,
            max_length=neobert_max_length,
            num_threads=neobert_threads,
            trust_remote_code=trust_remote_code,
        )
    else:
        rnsum_result = run_rnsum_overlap_proxy(rnsum_source, out_dir)

    return {
        "smartnote": smartnote_result,
        "rnsum": rnsum_result,
        "rnsum_proxy": rnsum_proxy,
        "max_features": max_features,
        "n_jobs": n_jobs,
    }
