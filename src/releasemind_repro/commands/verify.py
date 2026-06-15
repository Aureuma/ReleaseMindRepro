"""Command for reproducibility output validation."""

from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path

from releasemind_repro.commands import compare as compare_command
from releasemind_repro.commands._helpers import print_json
from releasemind_repro.pipeline.reference import load_manifest, validate_manifest_paths
from releasemind_repro.pipeline.schemas import validate_artifact, required_columns
from releasemind_repro.utils import row_count


def add_parser(subparsers, command: str) -> None:
    parser = subparsers.add_parser(command, help="Validate generated artifacts and optional reference comparison")
    parser.add_argument("--manifest", default=None, help="Path to reference manifest for comparison")
    parser.add_argument("--strict", action="store_true", help="Require non-empty files for all schema checks")
    parser.add_argument("--compare", action="store_true", help="Compare outputs against manifest when available")
    parser.add_argument("--skip-compare", action="store_true", help="Skip manifest comparison even when configured")
    parser.add_argument("--tolerance", type=float, default=0.0, help="Numeric tolerance for non-strict compare")
    parser.add_argument("--json", action="store_true", help="Emit JSON report")


def _schema_entries(config) -> list[tuple[str, Path, tuple[str, ...]]]:
    return [
        ("smartnote_proxy", config.smartnote_proxy_out, required_columns("smartnote_proxy")),
        ("rnsum_proxy", config.rnsum_proxy_out, required_columns("rnsum_proxy")),
        ("oracle_audit", config.oracle_out, required_columns("oracle_audit")),
        ("risk_summary", config.risk_eval_out, required_columns("risk_summary")),
        ("routing", config.routing_out, required_columns("routing")),
    ]


def _check_artifact(label: str, path: Path, required_columns: tuple[str, ...], *, strict: bool) -> dict[str, object]:
    result = validate_artifact(path, required_columns, strict=strict)
    payload: dict[str, object] = {
        "label": label,
        "path": str(path),
        "exists": path.exists(),
        "ok": bool(result.valid),
    }
    if not result.valid:
        payload["errors"] = list(result.errors)
    if path.exists():
        payload["rows"] = row_count(path)
        payload["bytes"] = path.stat().st_size
    return payload


def _print_console(report: dict[str, object]) -> None:
    print(f"verify ok: {report['ok']}")
    print("artifact_checks:")
    for check in report.get("artifact_checks", []):
        entry = check if isinstance(check, dict) else {}
        status = "ok" if entry.get("ok") else "FAIL"
        rows = entry.get("rows", "n/a")
        print(f" - {entry.get('label')}: {status} (rows={rows})")
        if not entry.get("ok"):
            for issue in entry.get("errors", []):
                print(f"   - {issue}")

    if "compare" in report and isinstance(report["compare"], dict):
        print(f"compare ok: {report['compare'].get('ok', False)}")


def run(args, config) -> dict[str, object]:
    report: dict[str, object] = {
        "ok": True,
        "config_root": str(config.root),
        "artifact_checks": [],
    }
    checks: list[dict[str, object]] = []

    for label, path, required in _schema_entries(config):
        check = _check_artifact(label, path, required, strict=args.strict)
        checks.append(check)
        if not check["ok"]:
            report["ok"] = False
    report["artifact_checks"] = checks

    manifest_path = Path(args.manifest or config.reference_manifest)
    compare_requested = bool(args.compare or (config.compare_reference and not args.skip_compare))

    if compare_requested:
        if not manifest_path.exists():
            report["ok"] = False
            report["compare"] = {
                "ok": False,
                "detail": f"manifest missing: {manifest_path}",
            }
        else:
            try:
                manifest = load_manifest(manifest_path)
                missing = validate_manifest_paths(manifest, config.root)
                compare_args = SimpleNamespace(
                    reference_dir=str(manifest_path.parent),
                    manifest=str(manifest_path),
                    strict=args.strict,
                    tolerance=args.tolerance,
                    json=False,
                )
                compare_report = compare_command.run(compare_args, config)
                report["compare"] = compare_report
                if not bool(compare_report.get("ok", False)):
                    report["ok"] = False

                if missing:
                    report["ok"] = False
                    report["compare"]["missing_reference_files"] = missing
            except Exception as exc:  # noqa: BLE001
                report["ok"] = False
                report["compare"] = {
                    "ok": False,
                    "error": str(exc),
                }

    elif args.skip_compare:
        report["compare"] = {"ok": True, "skipped": True}
    else:
        report["compare"] = {"ok": True, "skipped": True}

    if args.json:
        print_json(report)
    else:
        _print_console(report)
    return report
