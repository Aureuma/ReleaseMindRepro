"""Configuration loading and validation for ReleaseMind reproducibility runs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List, Mapping

import tomllib


@dataclass(frozen=True)
class RepoPaths:
    """Repository-level directory layout used by command defaults."""

    root: Path
    data_dir: Path
    fixtures_dir: Path
    outputs_dir: Path
    artifacts_dir: Path
    reference_dir: Path
    paper_compat_output_dir: Path


def _default_paths(root: Path) -> RepoPaths:
    root = Path(root).resolve()
    return RepoPaths(
        root=root,
        data_dir=root / "data",
        fixtures_dir=root / "data" / "fixtures",
        outputs_dir=root / "outputs",
        artifacts_dir=root / "artifacts",
        reference_dir=root / "artifacts" / "reference",
        paper_compat_output_dir=root / "output",
    )


def _coerce_str(value: object, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _coerce_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    return text in {"1", "true", "yes", "on", "y", "t"}


def _coerce_int(value: object, default: int) -> int:
    try:
        if isinstance(value, bool):
            return int(value)
        return int(value)
    except Exception:
        return default


def _coerce_float(value: object, default: float) -> float:
    try:
        if isinstance(value, bool):
            return float(int(value))
        return float(value)
    except Exception:
        return default


def _coerce_float_list(value: object) -> List[float]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        values: list[float] = []
        for item in value:
            try:
                values.append(float(item))
            except Exception:
                continue
        return values

    text = str(value).strip()
    if not text:
        return []

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


def _find_repo_root(start: Path) -> Path:
    base = start.resolve()
    if base.is_file():
        base = base.parent
    for candidate in [base, *base.parents]:
        if (candidate / "pyproject.toml").exists() and (candidate / "src" / "releasemind_repro").exists():
            return candidate
    return base


def _normalize_provider(value: object) -> str:
    provider = _coerce_str(value, "gemini").strip().lower()
    if provider in {"google", "google-genai"}:
        return "gemini"
    if provider in {"openai", "bedrock-runtime", "bedrock_runtime"}:
        if provider.startswith("bedrock"):
            return "bedrock"
    if provider in {"g", "gemini"}:
        return "gemini"
    return provider


def _normalize_mode(value: object) -> str:
    mode = _coerce_str(value, "standard").replace(" ", "_").lower()
    if mode in {"proxy", "proxy_only", "proxy-only", "standard"}:
        return "standard"
    if mode in {"tiered", "tiered_oracle", "tieredoracle"}:
        return "tiered_oracle"
    if mode in {"batch", "batch_job", "batch-mode"}:
        return "batch"
    if mode in {"none", "default"}:
        return "standard"
    return mode


def _normalize_rnsum_proxy(value: object) -> str:
    mode = _coerce_str(value, "overlap").lower()
    if mode in {"neobert", "neobert_proxy", "bert", "transformer"}:
        return "neobert"
    return "overlap"


def _normalize_proxy_model(value: object) -> str:
    mode = _coerce_str(value, "tfidf").lower()
    if mode in {"raw", "raw_model"}:
        return "raw"
    return "tfidf"


def _ensure_path(value: object, root: Path) -> Path:
    text = str(value).strip() if value is not None else ""
    if not text:
        return Path()
    candidate = Path(text)
    if candidate.is_absolute():
        return candidate
    return (Path(root) / candidate).resolve()


def _unique_sorted(values: Iterable[float]) -> List[float]:
    normalized = sorted({round(float(v), 10) for v in values})
    return [float(v) for v in normalized]


def _resolve_deltas(values: Iterable[float], step: float) -> List[float]:
    deltas = [float(value) for value in values if value is not None]
    if deltas:
        return _unique_sorted([value for value in deltas if 0.0 <= float(value) <= 1.0])

    if step <= 0:
        return [0.0, 1.0]
    max_points = int(round(1.0 / step))
    generated = [round(i * step, 10) for i in range(max_points + 1)]
    return _unique_sorted([value for value in generated if 0.0 <= value <= 1.0])


class ReproConfig:
    """Typed wrapper around TOML values with deterministic normalization."""

    def __init__(self, root: Path, values: Mapping[str, Any], source_path: Path | None = None):
        self.root = Path(root).resolve()
        self.values = dict(values)
        self._source_path = Path(source_path).resolve() if source_path is not None else self.root / "configs" / "paper.toml"
        self.paths = _default_paths(self.root)

    @property
    def audit_path(self) -> Path:
        return _ensure_path(self.values.get("audit_path", "outputs/audit"), self.root)

    def merge(self, overrides: Mapping[str, Any]) -> "ReproConfig":
        payload = dict(self.values)
        for key, value in overrides.items():
            if value is not None:
                payload[key] = value
        return ReproConfig(self.root, payload, source_path=self._source_path)

    @property
    def source_path(self) -> Path:
        return Path(self._source_path)

    def as_dict(self) -> dict[str, Any]:
        return dict(self.values)

    def fingerprint(self) -> str:
        payload = json.dumps(self.values, sort_keys=True, default=str, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    # core
    @property
    def sample_size(self) -> int:
        return max(0, _coerce_int(self.values.get("sample_size"), 3000))

    @property
    def seed(self) -> int:
        return _coerce_int(self.values.get("seed"), 42)

    @property
    def audit_frac(self) -> float:
        return _coerce_float(self.values.get("audit_frac"), 0.5)

    @property
    def continue_if_present(self) -> bool:
        return _coerce_bool(self.values.get("continue_if_present"), False)

    @property
    def overwrite(self) -> bool:
        return _coerce_bool(self.values.get("overwrite"), False)

    @property
    def compare_reference(self) -> bool:
        return _coerce_bool(self.values.get("compare_reference"), False)

    @property
    def compare_tolerance(self) -> float:
        return max(0.0, _coerce_float(self.values.get("compare_tolerance", self.values.get("tolerance")), 0.0))

    # provider and model controls
    @property
    def provider(self) -> str:
        return _normalize_provider(self.values.get("provider", self.values.get("audit_provider")))

    @property
    def audit_provider(self) -> str:
        return self.provider

    @property
    def model(self) -> str:
        return _coerce_str(self.values.get("model"), "models/gemini-2.5-pro")

    @property
    def oracle_mode(self) -> str:
        return _normalize_mode(self.values.get("oracle_mode", self.values.get("mode", "standard")))

    @property
    def mode(self) -> str:
        return self.oracle_mode

    @property
    def max_workers(self) -> int:
        return max(1, _coerce_int(self.values.get("max_workers"), 1))

    @property
    def max_retries(self) -> int:
        return max(0, _coerce_int(self.values.get("max_retries"), 3))

    @property
    def min_interval(self) -> float:
        return max(0.0, _coerce_float(self.values.get("min_interval"), 0.4))

    @property
    def batch_poll_interval(self) -> int:
        return max(1, _coerce_int(self.values.get("batch_poll_interval"), 30))

    @property
    def min_delay(self) -> float:
        return max(0.0, _coerce_float(self.values.get("min_delay", self.values.get("min_delay_seconds", 2.0)), 0.0))

    @property
    def temperature(self) -> float:
        return _coerce_float(self.values.get("temperature"), 0.0)

    @property
    def max_tokens(self) -> int:
        return max(1, _coerce_int(self.values.get("max_tokens"), 256))

    @property
    def skip_if_missing(self) -> bool:
        return _coerce_bool(self.values.get("skip_if_missing"), False)

    # paths
    @property
    def smartnote_dataset(self) -> Path:
        return _ensure_path(self.values.get("smartnote_dataset", "data/fixtures/smartnote_small.parquet"), self.root)

    @property
    def rnsum_dataset(self) -> Path:
        return _ensure_path(self.values.get("rnsum_dataset", "data/fixtures/rnsum_small.jsonl"), self.root)

    @property
    def smartnote_proxy_out(self) -> Path:
        return _ensure_path(self.values.get("smartnote_proxy_out", "outputs/risk_proxy/smartnote_proxy.parquet"), self.root)

    @property
    def rnsum_proxy_out(self) -> Path:
        return _ensure_path(self.values.get("rnsum_proxy_out", "outputs/risk_proxy/rnsum_proxy.parquet"), self.root)

    @property
    def smartnote_tfidf_model_out(self) -> Path:
        return _ensure_path(self.values.get("smartnote_tfidf_model_out", "outputs/risk_proxy/smartnote_tfidf_logreg.joblib"), self.root)

    @property
    def proxy_summary_out(self) -> Path:
        return _ensure_path(self.values.get("proxy_summary_out", "outputs/risk_proxy/proxy_summary.json"), self.root)

    @property
    def oracle_out(self) -> Path:
        return _ensure_path(self.values.get("oracle_out", "outputs/audit/oracle_audit.jsonl"), self.root)

    @property
    def oracle_summary_out(self) -> Path:
        return _ensure_path(self.values.get("oracle_summary_out", "outputs/audit/oracle_audit_summary.json"), self.root)

    @property
    def oracle_batch_dir(self) -> Path:
        return _ensure_path(self.values.get("oracle_batch_dir", "outputs/audit/batch"), self.root)

    @property
    def oracle_raw_out(self) -> Path:
        return _ensure_path(self.values.get("oracle_raw_out", "outputs/audit/oracle_audit_raw.jsonl"), self.root)

    @property
    def risk_eval_out(self) -> Path:
        return _ensure_path(self.values.get("risk_eval_out", "outputs/eval/risk_control_summary.csv"), self.root)

    @property
    def risk_eval_meta_out(self) -> Path:
        return _ensure_path(self.values.get("risk_eval_meta_out", "outputs/eval/risk_control_summary.meta.json"), self.root)

    @property
    def routing_out(self) -> Path:
        return _ensure_path(self.values.get("routing_out", "outputs/routing/simulate_routing.csv"), self.root)

    @property
    def figure_dir(self) -> Path:
        return _ensure_path(self.values.get("figure_dir", "outputs/figures"), self.root)

    @property
    def reference_manifest(self) -> Path:
        return _ensure_path(self.values.get("reference_manifest", "artifacts/reference/manifest.json"), self.root)

    @property
    def reference_run_meta(self) -> Path:
        return _ensure_path(self.values.get("reference_run_meta", "artifacts/reference/run-meta.json"), self.root)

    @property
    def reference_bundle_doc(self) -> Path:
        return _ensure_path(self.values.get("reference_bundle_doc", "artifacts/reference/reproducibility_bundle.md"), self.root)

    @property
    def publish_paper_layout(self) -> bool:
        return _coerce_bool(self.values.get("publish_paper_layout"), False)

    @property
    def publish_paper_output_root(self) -> Path:
        return _ensure_path(self.values.get("publish_paper_output_root", "output"), self.root)

    # model, sampling, and cost controls
    @property
    def tfidf_max_features(self) -> int:
        return max(1, _coerce_int(self.values.get("tfidf_max_features"), 3000))

    @property
    def n_jobs(self) -> int:
        return max(1, _coerce_int(self.values.get("n_jobs"), 1))

    @property
    def rnsum_proxy(self) -> str:
        return _normalize_rnsum_proxy(self.values.get("rnsum_proxy", self.values.get("neobert_proxy")))

    @property
    def rnsum_proxy_mode(self) -> str:
        return self.rnsum_proxy

    @property
    def neobert_model(self) -> str:
        return _coerce_str(self.values.get("neobert_model"), "chandar-lab/NeoBERT")

    @property
    def neobert_batch_size(self) -> int:
        return max(1, _coerce_int(self.values.get("neobert_batch_size"), 16))

    @property
    def neobert_max_length(self) -> int:
        return max(1, _coerce_int(self.values.get("neobert_max_length"), 128))

    @property
    def neobert_threads(self) -> int:
        return max(1, _coerce_int(self.values.get("neobert_threads"), 6))

    @property
    def trust_remote_code(self) -> bool:
        return _coerce_bool(self.values.get("trust_remote_code", True), True)

    @property
    def proxy_cost(self) -> float:
        return max(0.0, _coerce_float(self.values.get("proxy_cost"), 0.001))

    @property
    def oracle_cost(self) -> float:
        return max(0.0, _coerce_float(self.values.get("oracle_cost"), 1.0))

    @property
    def delta_step(self) -> float:
        return _coerce_float(self.values.get("delta_step"), 0.05)

    @property
    def deltas(self) -> List[float]:
        return _resolve_deltas(_coerce_float_list(self.values.get("deltas")), self.delta_step)

    @property
    def compare_corrections(self) -> bool:
        return _coerce_bool(self.values.get("compare_corrections"), False)

    @property
    def gap_quantile(self) -> float:
        return _coerce_float(self.values.get("gap_quantile"), 0.9)

    @property
    def proxy_model(self) -> str:
        return _normalize_proxy_model(self.values.get("proxy_model", self.values.get("proxy_score_model")))

    @property
    def correction_mode(self) -> str:
        return _coerce_str(self.values.get("correction", self.values.get("correction_mode", "none")), "none").lower()

    @property
    def ci_alpha(self) -> float:
        return _coerce_float(self.values.get("ci_alpha"), 0.05)

    @property
    def baselines_random_state(self) -> int:
        return _coerce_int(self.values.get("baselines_random_state"), 42)

    @property
    def paths_root(self) -> Path:
        return self.paths.root

    @property
    def outputs_dir(self) -> Path:
        return self.paths.outputs_dir

    @property
    def reference_dir(self) -> Path:
        return self.paths.reference_dir

    @property
    def required_outputs(self) -> tuple[Path, ...]:
        return (
            self.smartnote_proxy_out,
            self.rnsum_proxy_out,
            self.smartnote_tfidf_model_out,
            self.proxy_summary_out,
            self.oracle_out,
            self.oracle_summary_out,
            self.oracle_raw_out,
            self.risk_eval_out,
            self.risk_eval_meta_out,
            self.routing_out,
            self.figure_dir / "risk_control_curve_smartnote.pdf",
            self.figure_dir / "risk_control_curve_rnsum.pdf",
            self.figure_dir / "routing_cost_risk_smartnote.pdf",
            self.figure_dir / "routing_cost_risk_rnsum.pdf",
        )

    @property
    def compatibility_output_map(self) -> dict[str, Path]:
        return {
            "risk_proxy/smartnote_proxy.parquet": self.smartnote_proxy_out,
            "risk_proxy/rnsum_proxy.parquet": self.rnsum_proxy_out,
            "risk_proxy/smartnote_tfidf_logreg.joblib": self.smartnote_tfidf_model_out,
            "risk_proxy/proxy_summary.json": self.proxy_summary_out,
            "audit/oracle_audit.jsonl": self.oracle_out,
            "audit/oracle_audit_summary.json": self.oracle_summary_out,
            "audit/oracle_audit_raw.jsonl": self.oracle_raw_out,
            "eval/risk_control_summary.csv": self.risk_eval_out,
            "eval/risk_control_summary.meta.json": self.risk_eval_meta_out,
            "routing/simulate_routing.csv": self.routing_out,
            "figures/risk_control_curve_smartnote.pdf": self.figure_dir / "risk_control_curve_smartnote.pdf",
            "figures/risk_control_curve_rnsum.pdf": self.figure_dir / "risk_control_curve_rnsum.pdf",
            "figures/routing_cost_risk_smartnote.pdf": self.figure_dir / "routing_cost_risk_smartnote.pdf",
            "figures/routing_cost_risk_rnsum.pdf": self.figure_dir / "routing_cost_risk_rnsum.pdf",
        }

    @property
    def output_artifacts(self) -> dict[str, Path]:
        return {
            **self.compatibility_output_map,
            "smartnote_proxy": self.smartnote_proxy_out,
            "rnsum_proxy": self.rnsum_proxy_out,
            "smartnote_tfidf_model": self.smartnote_tfidf_model_out,
            "proxy_summary": self.proxy_summary_out,
            "oracle_jsonl": self.oracle_out,
            "oracle_summary": self.oracle_summary_out,
            "oracle_raw": self.oracle_raw_out,
            "risk_summary": self.risk_eval_out,
            "risk_meta": self.risk_eval_meta_out,
            "routing": self.routing_out,
        }

    @property
    def manifest_entries(self) -> List[Path]:
        return list(self.output_artifacts.values())

    @property
    def output_root(self) -> Path:
        return self.outputs_dir

    @property
    def manifest_map(self) -> dict[str, str]:
        return {str(path.relative_to(self.root)): str(path) for path in self.manifest_entries}

    @property
    def known_fields(self) -> set[str]:
        return {
            "sample_size",
            "seed",
            "audit_frac",
            "continue_if_present",
            "overwrite",
            "audit_path",
            "compare_reference",
            "compare_tolerance",
            "provider",
            "audit_provider",
            "model",
            "oracle_mode",
            "mode",
            "max_workers",
            "max_retries",
            "min_interval",
            "batch_poll_interval",
            "min_delay",
            "temperature",
            "max_tokens",
            "skip_if_missing",
            "smartnote_dataset",
            "rnsum_dataset",
            "smartnote_proxy_out",
            "rnsum_proxy_out",
            "smartnote_tfidf_model_out",
            "proxy_summary_out",
            "oracle_out",
            "oracle_summary_out",
            "oracle_batch_dir",
            "oracle_raw_out",
            "risk_eval_out",
            "risk_eval_meta_out",
            "routing_out",
            "figure_dir",
            "reference_manifest",
            "reference_run_meta",
            "reference_bundle_doc",
            "publish_paper_layout",
            "publish_paper_output_root",
            "tfidf_max_features",
            "n_jobs",
            "rnsum_proxy",
            "neobert_proxy",
            "neobert_model",
            "neobert_batch_size",
            "neobert_max_length",
            "neobert_threads",
            "trust_remote_code",
            "proxy_cost",
            "oracle_cost",
            "delta_step",
            "deltas",
            "compare_corrections",
            "gap_quantile",
            "proxy_model",
            "correction",
            "correction_mode",
            "ci_alpha",
            "baselines_random_state",
        }

    def validate(self, strict: bool = False) -> list[str]:
        warnings: list[str] = []

        unknown = set(self.values.keys()) - self.known_fields
        if unknown:
            warnings.append(f"unknown config keys: {sorted(unknown)}")

        if self.sample_size < 0:
            warnings.append("sample_size must be >= 0")

        if not (0 < self.audit_frac <= 1):
            warnings.append("audit_frac must be in (0, 1]")

        if self.oracle_mode not in {"standard", "batch", "tiered_oracle"}:
            warnings.append("mode must be one of standard, batch, tiered_oracle")

        if self.provider not in {"gemini", "bedrock"}:
            warnings.append("provider must be one of gemini or bedrock")

        if self.rnsum_proxy not in {"overlap", "neobert"}:
            warnings.append("rnsum_proxy must be overlap or neobert")

        if self.proxy_model not in {"raw", "tfidf"}:
            warnings.append("proxy_model must be raw or tfidf")

        if self.proxy_cost < 0.0:
            warnings.append("proxy_cost must be >= 0")

        if self.oracle_cost < 0.0:
            warnings.append("oracle_cost must be >= 0")

        if not (0 < self.delta_step <= 1):
            warnings.append("delta_step must be in (0, 1]")

        if not self.deltas:
            warnings.append("deltas must contain at least one value")

        if not (0 <= self.gap_quantile <= 1):
            warnings.append("gap_quantile must be in [0, 1]")

        if self.compare_tolerance < 0:
            warnings.append("compare_tolerance must be >= 0")

        if not (0 < self.ci_alpha < 1):
            warnings.append("ci_alpha must be in (0, 1)")

        if strict:
            for value in [self.smartnote_dataset, self.rnsum_dataset]:
                if not value.exists():
                    warnings.append(f"missing required dataset: {value}")

            for required in [
                self.smartnote_dataset,
                self.rnsum_dataset,
                self.smartnote_proxy_out,
                self.rnsum_proxy_out,
                self.oracle_out,
                self.risk_eval_out,
                self.routing_out,
                self.reference_manifest,
            ]:
                if required in {Path()}:
                    continue
                if not required.exists():
                    warnings.append(f"required file missing: {required}")

            for path in [
                self.smartnote_proxy_out.parent,
                self.rnsum_proxy_out.parent,
                self.oracle_batch_dir,
                self.risk_eval_out.parent,
                self.routing_out.parent,
                self.figure_dir,
                self.reference_dir,
            ]:
                if path.exists() and not path.is_dir():
                    warnings.append(f"expected directory path but got file: {path}")

        return warnings


def load_config(config_path: Path, root: Path | None = None) -> ReproConfig:
    path = Path(config_path)
    if not path.is_absolute():
        path = Path.cwd() / path

    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with path.open("rb") as stream:
        values = tomllib.load(stream)

    explicit_root = Path(root).resolve() if root is not None else None
    repo_root = explicit_root if explicit_root is not None else _find_repo_root(path)
    return ReproConfig(repo_root, values, source_path=path)
