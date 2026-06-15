"""End-to-end reproduction orchestration command."""

from __future__ import annotations

import shutil
import time
from pathlib import Path

from releasemind_repro.adapters.paper_eval import run as run_eval
from releasemind_repro.adapters.paper_oracle import run as run_audit
from releasemind_repro.adapters.paper_simulate import run as run_simulate
from releasemind_repro.adapters.paper_train import run as run_train
from releasemind_repro.commands._helpers import make_step_result, merge_if_supplied, print_json
from releasemind_repro.utils import row_count


def add_parser(subparsers, command: str) -> None:
    parser = subparsers.add_parser(command, help="Run full reproducibility pipeline")
    parser.add_argument("--skip-train", action="store_true")
    parser.add_argument("--skip-audit", action="store_true")
    parser.add_argument("--skip-evaluate-risk", action="store_true")
    parser.add_argument("--skip-simulate", action="store_true")
    parser.add_argument("--continue-if-present", action="store_true")
    parser.add_argument("--publish-paper-layout", action="store_true")
    parser.add_argument("--audit-provider", choices=["gemini", "bedrock"], default=None)
    parser.add_argument("--audit-model", default=None)
    parser.add_argument("--audit-mode", choices=["standard", "batch", "tiered_oracle", "proxy_only"], default=None)
    parser.add_argument("--sample-size", type=int, default=None)
    parser.add_argument("--json", action="store_true")


def _exists(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


def _jsonl_count(path: Path) -> int | None:
    return row_count(path)


def _validate_existing(path: Path, required: str) -> bool:
    if not path.exists():
        return False
    if required in {"jsonl", "parquet", "csv"}:
        count = _jsonl_count(path)
        if count is None:
            return path.stat().st_size > 0
        return count > 0
    return path.stat().st_size > 0


def _step_ready(name: str, cfg) -> bool:
    if name == "train-proxies":
        return _validate_existing(cfg.smartnote_proxy_out, "parquet") and _validate_existing(cfg.rnsum_proxy_out, "parquet")
    if name == "audit":
        return _validate_existing(cfg.oracle_out, "jsonl")
    if name == "evaluate-risk":
        return _validate_existing(cfg.risk_eval_out, "csv") and _validate_existing(cfg.risk_eval_meta_out, "json")
    if name == "simulate-routing":
        return _validate_existing(cfg.routing_out, "csv")
    return False


def _run_step(name: str, fn, cfg, *, args, preconditions: list[tuple[str, Path]]) -> dict[str, object]:
    if args.continue_if_present and _step_ready(name, cfg):
        return make_step_result("skipped", step=name, reason="already_present")

    for parent_name, required in preconditions:
        if not _exists(required):
            raise RuntimeError(f"upstream dependency missing for {name}: {parent_name} -> {required}")

    start_ms = int(time.time() * 1000)
    payload = fn(cfg)
    if isinstance(payload, dict):
        payload = dict(payload)
        payload["status"] = "ok"
    else:
        payload = {"status": "ok", "result": payload}
    payload["step"] = name
    payload["duration_ms"] = max(0, int(time.time() * 1000) - start_ms)
    return make_step_result("ok", **payload)


def _publish_layout(cfg) -> dict[str, str]:
    copied: dict[str, str] = {}
    for rel, source in cfg.compatibility_output_map.items():
        source_path = Path(source)
        if not source_path.exists():
            continue
        destination = cfg.publish_paper_output_root / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination)
        copied[str(source_path)] = str(destination)
    return copied


def _require_inputs_for_step(step: str, cfg) -> list[tuple[str, Path]]:
    if step == "train":
        return []
    if step == "audit":
        return [("smartnote_proxy", cfg.smartnote_proxy_out), ("rnsum_proxy", cfg.rnsum_proxy_out)]
    if step == "evaluate-risk":
        return [("oracle_audit", cfg.oracle_out)]
    if step == "simulate":
        return [("oracle_audit", cfg.oracle_out)]
    return []


def run(args, config) -> dict:
    updates = {
        "provider": args.audit_provider,
        "model": args.audit_model,
        "oracle_mode": args.audit_mode,
        "sample_size": args.sample_size,
        "continue_if_present": args.continue_if_present,
        "publish_paper_layout": bool(args.publish_paper_layout),
    }
    cfg = merge_if_supplied(config, updates)
    report: dict[str, object] = {
        "ok": True,
        "steps": {},
    }
    steps: dict[str, object] = {}

    try:
        if not args.skip_train:
            steps["train-proxies"] = _run_step(
                "train-proxies",
                lambda run_cfg: run_train(run_cfg),
                cfg,
                args=args,
                preconditions=[],
            )

        if not args.skip_audit:
            steps["audit"] = _run_step(
                "audit",
                lambda run_cfg: run_audit(
                    run_cfg,
                    sample_size_override=args.sample_size,
                    mode_override=args.audit_mode,
                    provider_override=args.audit_provider,
                    model_override=args.audit_model,
                    skip_if_missing=False,
                ),
                cfg,
                args=args,
                preconditions=_require_inputs_for_step("audit", cfg),
            )

        if not args.skip_evaluate_risk:
            steps["evaluate-risk"] = _run_step(
                "evaluate-risk",
                lambda run_cfg: run_eval(run_cfg),
                cfg,
                args=args,
                preconditions=_require_inputs_for_step("evaluate-risk", cfg),
            )

        if not args.skip_simulate:
            steps["simulate-routing"] = _run_step(
                "simulate-routing",
                lambda run_cfg: run_simulate(run_cfg),
                cfg,
                args=args,
                preconditions=_require_inputs_for_step("simulate", cfg),
            )

    except Exception as exc:  # noqa: BLE001
        report.update(
            {
                "ok": False,
                "failed_step": True,
                "error": str(exc),
                "steps": steps,
            }
        )
        if args.json:
            print_json(report)
        return report

    if cfg.publish_paper_layout:
        copied = _publish_layout(cfg)
    else:
        copied = {}

    report["steps"] = steps
    report["paper_layout"] = copied
    report["duration_ms"] = sum(
        int(item.get("duration_ms", 0))
        for item in steps.values()
        if isinstance(item, dict)
    )
    if args.json:
        print_json(report)
    else:
        for step, info in steps.items():
            status = info.get("status") if isinstance(info, dict) else "ok"
            if isinstance(info, dict) and "rows" in info:
                status = f"rows={info.get('rows')}"
            print(f"{step}: {status}")
        if copied:
            print(f"published outputs to {cfg.publish_paper_output_root}")
    return report
