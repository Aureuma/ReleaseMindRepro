import json
from pathlib import Path
from types import SimpleNamespace

from releasemind_repro.commands import verify
from releasemind_repro.config import load_config


def _write_minimal_config(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                'sample_size = 4',
                'seed = 1',
                'audit_frac = 0.5',
                'smartnote_dataset = "data/fixtures/smartnote_small.parquet"',
                'rnsum_dataset = "data/fixtures/rnsum_small.jsonl"',
                'smartnote_proxy_out = "outputs/risk_proxy/smartnote_proxy.csv"',
                'rnsum_proxy_out = "outputs/risk_proxy/rnsum_proxy.csv"',
                'smartnote_tfidf_model_out = "outputs/risk_proxy/smartnote_tfidf_logreg.joblib"',
                'proxy_summary_out = "outputs/risk_proxy/proxy_summary.json"',
                'oracle_out = "outputs/audit/oracle_audit.jsonl"',
                'oracle_summary_out = "outputs/audit/oracle_audit_summary.json"',
                'oracle_batch_dir = "outputs/audit/batch"',
                'oracle_raw_out = "outputs/audit/oracle_audit_raw.jsonl"',
                'risk_eval_out = "outputs/eval/risk_control_summary.csv"',
                'risk_eval_meta_out = "outputs/eval/risk_control_summary.meta.json"',
                'routing_out = "outputs/routing/simulate_routing.csv"',
                'figure_dir = "outputs/figures"',
                'reference_manifest = "artifacts/reference/manifest.json"',
                'reference_run_meta = "artifacts/reference/run-meta.json"',
            ]
        ),
        encoding="utf-8",
    )


def _write_artifacts(root: Path) -> None:
    (root / "outputs/risk_proxy").mkdir(parents=True, exist_ok=True)
    (root / "outputs/audit").mkdir(parents=True, exist_ok=True)
    (root / "outputs/eval").mkdir(parents=True, exist_ok=True)
    (root / "outputs/routing").mkdir(parents=True, exist_ok=True)
    (root / "outputs/figures").mkdir(parents=True, exist_ok=True)

    (root / "outputs/risk_proxy/smartnote_proxy.csv").write_text(
        "body,isInRN,risk_score\nabc,1,0.2\n", encoding="utf-8"
    )
    (root / "outputs/risk_proxy/rnsum_proxy.csv").write_text(
        "input_text,target_text,risk_score\na,b,0.3\n", encoding="utf-8"
    )
    (root / "outputs/audit/oracle_audit.jsonl").write_text(
        json.dumps(
            {
                "audit_id": "smartnote_0",
                "dataset": "smartnote",
                "proxy_score": 0.3,
                "oracle_label": 1,
                "raw_output": "ok",
                "parsed_output": {"label": 1},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "outputs/routing/simulate_routing.csv").write_text(
        "delta,oracle_calls,total,cost,avg_cost,risk,dataset,proxy_model\n"
        "0.3,1,2,2.0,1.0,0.2,smartnote,tfidf\n",
        encoding="utf-8",
    )


def test_verify_reports_missing_artifacts(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / "src" / "releasemind_repro").mkdir(parents=True)
    (repo_root / "pyproject.toml").write_text("[project]\nname = 'tmp'\nversion = '0.0.1'\n", encoding="utf-8")

    config_path = repo_root / "configs" / "paper_smoke.toml"
    _write_minimal_config(config_path)

    cfg = load_config(config_path)
    _write_artifacts(repo_root)

    args = SimpleNamespace(manifest=None, strict=True, compare=False, skip_compare=True, tolerance=0.0, json=False)
    report = verify.run(args, cfg)

    assert report["ok"] is False
    checks = {entry["label"]: entry for entry in report["artifact_checks"]}
    assert checks["risk_summary"]["ok"] is False
