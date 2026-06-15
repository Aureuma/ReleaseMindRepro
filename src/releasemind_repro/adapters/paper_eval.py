"""Adapter layer for risk-control evaluation and plotting."""

from __future__ import annotations

import json
from typing import Dict, List, Tuple

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from releasemind_repro.style import apply_theme
from releasemind_repro.utils import clopper_pearson

BINS = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]


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


def _compute_bin_eps(df: pd.DataFrame, bins: List[float], quantile: float) -> Tuple[Dict[str, float], float]:
    if df.empty:
        return {}, 0.0

    df = df.copy()
    df["error"] = (pd.to_numeric(df["oracle_label"], errors="coerce") - pd.to_numeric(df["proxy_score"], errors="coerce")).abs()
    df["bin"] = pd.cut(df["proxy_score"], bins=bins, include_lowest=True, right=True)

    bin_eps: Dict[str, float] = {}
    for key, group in df.groupby("bin", dropna=False):
        if group.empty:
            continue
        errors = pd.to_numeric(group["error"], errors="coerce")
        bin_eps[str(key)] = float(errors.quantile(quantile))

    global_eps = float(df["error"].quantile(quantile))
    intervals = pd.IntervalIndex.from_breaks(bins, closed="right")
    for interval in intervals:
        key = str(interval)
        bin_eps.setdefault(key, global_eps)
    return bin_eps, global_eps


def _apply_correction(df: pd.DataFrame, bins: List[float], bin_eps: Dict[str, float]) -> pd.DataFrame:
    result = df.copy()
    result["bin"] = pd.cut(result["proxy_score"], bins=bins, include_lowest=True, right=True).astype(str)
    result["epsilon"] = result["bin"].map(bin_eps).fillna(0.0)
    result["score_corrected"] = (result["proxy_score"] + result["epsilon"]).clip(lower=0.0, upper=1.0)
    return result


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


def run(cfg) -> Dict[str, object]:
    apply_theme()

    df = _load_audit(cfg.oracle_out)
    if df.empty:
        out = cfg.risk_eval_out
        out.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(
            columns=[
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
            ]
        ).to_csv(out, index=False)
        meta = {
            "generated_with": "evaluate-risk",
            "audit_meta": [],
            "bins": BINS,
            "deltas": cfg.deltas,
            "mode": cfg.mode,
            "compare_corrections": cfg.compare_corrections,
            "gap_quantile": cfg.gap_quantile,
            "seed": cfg.seed,
            "audit_frac": cfg.audit_frac,
            "ci_alpha": cfg.ci_alpha,
            "reason": "no_oracle_labels",
        }
        cfg.risk_eval_meta_out.parent.mkdir(parents=True, exist_ok=True)
        cfg.risk_eval_meta_out.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        return {"rows": 0, "output": str(cfg.risk_eval_out), "meta": str(cfg.risk_eval_meta_out)}

    audit_frac = cfg.audit_frac
    if not 0 < audit_frac <= 1:
        raise ValueError(f"Invalid audit_frac {audit_frac}")

    deltas = cfg.deltas
    if not deltas:
        raise ValueError("No deltas configured")

    results: list[dict] = []
    audit_meta: list[dict] = []

    for dataset in sorted(df["dataset"].dropna().unique()):
        dataset_rows = df[df["dataset"] == dataset].dropna(subset=["oracle_label", "proxy_score"]).copy()
        if dataset_rows.empty:
            raise ValueError(f"No labeled rows for dataset {dataset}")

        dataset_rows = dataset_rows.sample(frac=1.0, random_state=cfg.seed).reset_index(drop=True)
        split_idx = int(len(dataset_rows) * audit_frac)
        if split_idx <= 0 or split_idx >= len(dataset_rows):
            raise ValueError(
                "Split produced empty train or test partition; increase sample size or lower audit_frac. "
                f"dataset={dataset}, rows={len(dataset_rows)}, audit_frac={audit_frac}"
            )

        audit_df = dataset_rows.iloc[:split_idx].copy()
        test_df = dataset_rows.iloc[split_idx:].copy()

        if cfg.proxy_model == "tfidf":
            model = _fit_tfidf_proxy(audit_df, dataset, cfg.tfidf_max_features)
            audit_df = audit_df.copy()
            test_df = test_df.copy()
            audit_df["proxy_score"] = model.predict_proba(_build_text_features(audit_df, dataset))[:, 1]
            test_df["proxy_score"] = model.predict_proba(_build_text_features(test_df, dataset))[:, 1]

        corrections = ["none"]
        if cfg.compare_corrections:
            corrections.append("bin_gap")
        else:
            corrections = [cfg.correction_mode]

        for correction in corrections:
            if correction == "bin_gap":
                bin_eps, global_eps = _compute_bin_eps(audit_df, BINS, cfg.gap_quantile)
                corrected = _apply_correction(test_df, BINS, bin_eps)
            else:
                global_eps = 0.0
                corrected = test_df.copy()
                corrected["score_corrected"] = corrected["proxy_score"]

            audit_meta.append(
                {
                    "dataset": dataset,
                    "n_total": int(len(dataset_rows)),
                    "n_audit": int(len(audit_df)),
                    "n_test": int(len(test_df)),
                    "global_eps": float(global_eps),
                    "gap_quantile": cfg.gap_quantile if correction == "bin_gap" else None,
                    "proxy_model": cfg.proxy_model,
                    "correction": correction,
                }
            )

            for delta in deltas:
                low_risk = corrected["score_corrected"] <= delta
                if cfg.mode == "tiered_oracle":
                    accept_mask = low_risk | ((~low_risk) & (corrected["oracle_label"] == 0))
                else:
                    accept_mask = low_risk

                accepted = corrected[accept_mask]
                n_accept = int(len(accepted))
                n_total = int(len(corrected))
                violations = int((accepted["oracle_label"] == 1).sum()) if n_accept else 0
                risk_rate = violations / n_accept if n_accept > 0 else float("nan")
                ci_low, ci_high = clopper_pearson(violations, n_accept, alpha=cfg.ci_alpha)
                oracle_calls = int((~low_risk).sum()) if cfg.mode == "tiered_oracle" else 0
                variant = "proxy-only" if correction == "none" else f"gap-p{int(cfg.gap_quantile * 100)}"

                results.append({
                    "dataset": dataset,
                    "variant": variant,
                    "delta": float(delta),
                    "n_total": n_total,
                    "n_accept": n_accept,
                    "coverage": float(n_accept / n_total) if n_total else 0.0,
                    "violations": violations,
                    "risk_rate": float(risk_rate),
                    "risk_ci_low": float(ci_low),
                    "risk_ci_high": float(ci_high),
                    "oracle_calls": oracle_calls,
                })

    out = cfg.risk_eval_out
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(results).to_csv(out, index=False)

    meta = {
        "generated_with": "evaluate-risk",
        "audit_meta": audit_meta,
        "bins": BINS,
        "deltas": deltas,
        "mode": cfg.mode,
        "compare_corrections": cfg.compare_corrections,
        "gap_quantile": cfg.gap_quantile,
        "seed": cfg.seed,
        "audit_frac": cfg.audit_frac,
        "ci_alpha": cfg.ci_alpha,
    }
    cfg.risk_eval_meta_out.parent.mkdir(parents=True, exist_ok=True)
    cfg.risk_eval_meta_out.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    # Per-dataset figures
    if not pd.DataFrame(results).empty:
        import matplotlib.pyplot as plt

        results_df = pd.DataFrame(results)
        for dataset in results_df["dataset"].unique():
            subset = results_df[results_df["dataset"] == dataset]
            if subset.empty:
                continue
            numeric = subset.copy()
            figure_data = numeric[numeric["delta"].apply(lambda v: isinstance(v, float))]

            fig, axes = plt.subplots(2, 1, figsize=(5.4, 4.8), sharex=True)
            for variant in sorted(figure_data["variant"].unique()):
                variant_rows = figure_data[figure_data["variant"] == variant].sort_values("delta")
                if variant == "proxy-only":
                    color = "#1F6FEB"
                else:
                    color = "#0F766E"
                axes[0].plot(variant_rows["delta"], variant_rows["risk_rate"], marker="o", label=variant, color=color)
                axes[0].fill_between(
                    variant_rows["delta"],
                    variant_rows["risk_ci_low"],
                    variant_rows["risk_ci_high"],
                    alpha=0.15,
                    color=color,
                )
                axes[1].plot(variant_rows["delta"], variant_rows["coverage"], marker="o", color=color, label=variant)

            axes[0].set_ylabel("Risk violation rate")
            axes[1].set_ylabel("Coverage")
            axes[1].set_xlabel(r"Threshold \delta")
            axes[0].set_title(f"Risk control ({dataset})")
            axes[0].legend(fontsize=8, frameon=False)
            fig.tight_layout()

            target = cfg.figure_dir / f"risk_control_curve_{dataset}.pdf"
            target.parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(target)
            plt.close(fig)

    return {
        "rows": int(len(results)),
        "output": str(cfg.risk_eval_out),
        "meta": str(cfg.risk_eval_meta_out),
    }
