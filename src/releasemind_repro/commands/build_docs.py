"""Build reference manifest and reproducibility metadata files."""

from __future__ import annotations

import platform
import time
from pathlib import Path

from releasemind_repro.commands._helpers import print_json, write_lines
from releasemind_repro.pipeline.reference import REFERENCE_MANIFEST_VERSION, build_manifest, write_manifest


def add_parser(subparsers, command: str) -> None:
    parser = subparsers.add_parser(command, help="Build manifests and reproducibility bundle docs")
    parser.add_argument("--manifest", dest="manifest", default="artifacts/reference/manifest.json")
    parser.add_argument("--run-meta", dest="run_meta", default="artifacts/reference/run-meta.json")
    parser.add_argument("--docs", dest="docs_path", default="artifacts/reference/reproducibility_bundle.md")


def run(args, config) -> dict:
    manifest_path = Path(args.manifest)
    run_meta_path = Path(args.run_meta)
    docs_path = Path(args.docs_path)

    manifest = build_manifest(config.root, config.manifest_entries)
    write_manifest(manifest, manifest_path)
    generated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    run_meta = {
        "generated_at": generated_at,
        "command": f"releasemind-repro build-docs --config {config.source_path}",
        "config_hash": config.fingerprint(),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "artifact_count": len(manifest.files),
        "artifact_root": str(config.output_root.relative_to(config.root)),
        "repository": "ReleaseMindRepro",
        "reference_manifest_version": REFERENCE_MANIFEST_VERSION,
        "reference_manifest": str(manifest_path),
    }
    run_meta_path.parent.mkdir(parents=True, exist_ok=True)
    run_meta_path.write_text(__import__("json").dumps(run_meta, indent=2), encoding="utf-8")

    lines = [
        "# ReleaseMindRepro Reproducibility Bundle",
        "",
        f"Generated at: {generated_at}",
        f"Config fingerprint: {run_meta['config_hash']}",
        "",
        "## Output inventory",
        f"Generated command: `{run_meta['command']}`",
        f"Reference manifest: `{manifest_path}`",
        "",
    ]
    for path in sorted([str(item) for item in config.output_artifacts.keys()]):
        lines.append(f"- {path}")

    lines += [
        "",
        "## Reference verification",
        f"Run `releasemind-repro compare --config {config.source_path}` to validate outputs.",
    ]
    write_lines(lines, docs_path)

    report = {"ok": True, "manifest": str(manifest_path), "run_meta": str(run_meta_path), "docs": str(docs_path)}
    print_json(report)
    return report
