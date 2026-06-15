"""Adapter layer for routing simulation and plotting."""

from __future__ import annotations

import json
from typing import Dict, List

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from releasemind_repro.style import apply_theme


def _load_audit(path) -> pd.DataFrame:
    rows = []
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("oracle_label") is None:
                continue
            rows.append(row)
    return pd.DataFrame(rows)


def _build_text_features(df: pd.DataFrame, dataset: str) -> pd.Series:
    if dataset == "rnsum":
        return df["input_text"].fillna("").astype(str) + "\n" + df["target_text"].fillna("").astype(str)
    return df["body"].fillna("").astype(str)


def _fit_tfidf_proxy(df: pd.DataFrame, dataset: str, max_features: int):
    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(max_features=max_features, stop_words="english")),
        ("clf", LogisticRegression(max_iter=1000, class_weight="balanced")),
    ])
    text = _build_text_features(df, dataset)
    pipeline.fit(text, df["oracle_label"].astype(int))
    return pipeline


def _simulate(df: pd.DataFrame, deltas: List[float], proxy_cost: float, oracle_cost: float) -> List[Dict]:
    rows: list[dict] = []
    total = int(len(df))
    if total == 0:
        return rows

    for delta in deltas:
        oracle_calls = int((df["proxy_score"] > delta).sum())
        failures = int(((df["proxy_score"] <= delta) & (df["oracle_label"] == 1)).sum())
        cost = total * proxy_cost + oracle_calls * oracle_cost
        avg_cost = cost / total
        risk = failures / total
        rows.append({
            "delta": float(delta),
            "oracle_calls": int(oracle_calls),
            "total": total,
            "cost": float(cost),
            "avg_cost": float(avg_cost),
            "risk": float(risk),
        })

    rows.append({
        "delta": "verify_none",
        "oracle_calls": 0,
        "total": total,
        "cost": float(total * proxy_cost),
        "avg_cost": float(proxy_cost),
        "risk": float(df["oracle_label"].mean()),
    })
    rows.append({
        "delta": "verify_all",
        "oracle_calls": total,
        "total": total,
        "cost": float(total * (proxy_cost + oracle_cost)),
        "avg_cost": float(proxy_cost + oracle_cost),
        "risk": 0.0,
    })
    return rows


def _plot(df: pd.DataFrame, out_path: str) -> None:
    import matplotlib.pyplot as plt

    numeric = df[df["delta"].apply(lambda value: isinstance(value, float))].copy()
    if numeric.empty:
        return
    fig, ax = plt.subplots(figsize=(5.4, 3.2))
    ax.plot(numeric["avg_cost"], numeric["risk"], marker="o", color="#0F766E")
    ax.set_xlabel("Avg cost (normalized)")
    ax.set_ylabel("Risk violation rate")
    ax.set_title(f"Cost vs Risk ({out_path.split('_')[-1].replace('.pdf', '')})")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def run(cfg) -> Dict[str, object]:
    apply_theme()

    audit = _load_audit(cfg.oracle_out)
    if audit.empty:
        raise ValueError("No audited rows with labels. Run audit first.")

    deltas = [round(i * cfg.delta_step, 2) for i in range(int(1 / cfg.delta_step) + 1)]
    all_rows: list[dict] = []

    for dataset in sorted(audit["dataset"].dropna().unique()):
        subset = audit[audit["dataset"] == dataset].copy()
        if subset.empty:
            continue

        if cfg.proxy_model == "tfidf":
            model = _fit_tfidf_proxy(subset, dataset, cfg.tfidf_max_features)
            subset = subset.copy()
            subset["proxy_score"] = model.predict_proba(_build_text_features(subset, dataset))[:, 1]

        rows = _simulate(subset, deltas, cfg.proxy_cost, cfg.oracle_cost)
        for row in rows:
            row["dataset"] = dataset
            row["proxy_model"] = cfg.proxy_model
        all_rows.extend(rows)

        dataset_df = pd.DataFrame(rows)
        _plot(dataset_df, str(cfg.figure_dir / f"routing_cost_risk_{dataset}.pdf"))

    out = cfg.routing_out
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(all_rows).to_csv(out, index=False)
    return {"rows": len(all_rows), "output": str(out)}
