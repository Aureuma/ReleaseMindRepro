"""Reference artifact manifest support for reproducibility runs."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List

from releasemind_repro.utils import checksum, row_count


REFERENCE_MANIFEST_VERSION = "reproducibility-manifest/1"


class FileLookupError(RuntimeError):
    """Raised when a manifest entry cannot be located."""


@dataclass(frozen=True)
class ReferenceFile:
    path: str
    sha256: str
    rows: int | None = None
    bytes: int | None = None


@dataclass(frozen=True)
class ReferenceManifest:
    version: str
    files: List[ReferenceFile]

    def to_json(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "files": [asdict(item) for item in self.files],
        }


def load_manifest(manifest_path: Path) -> ReferenceManifest:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    files: list[ReferenceFile] = []
    for row in payload.get("files", []):
        sha256 = row.get("sha256") or ""
        files.append(
            ReferenceFile(
                path=row["path"],
                sha256=str(sha256),
                rows=row.get("rows"),
                bytes=row.get("bytes"),
            )
        )
    version = payload.get("version", "")
    if not version:
        raise FileLookupError("Invalid manifest: missing version")
    return ReferenceManifest(version=version, files=files)


def build_manifest(root: Path, entries: Iterable[Path]) -> ReferenceManifest:
    files: list[ReferenceFile] = []
    for path in entries:
        if not path.exists():
            continue
        files.append(
            ReferenceFile(
                path=str(path.relative_to(root)).replace("\\", "/"),
                sha256=checksum(path),
                rows=row_count(path),
                bytes=path.stat().st_size,
            )
        )
    return ReferenceManifest(version=REFERENCE_MANIFEST_VERSION, files=files)


def build_manifest_from_config(root: Path, entries: Iterable[Path]) -> ReferenceManifest:
    return build_manifest(root, entries)


def write_manifest(manifest: ReferenceManifest, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest.to_json(), indent=2), encoding="utf-8")


def file_lookup(manifest: ReferenceManifest) -> dict[str, ReferenceFile]:
    return {item.path: item for item in manifest.files}


def merge_file_rows(left: ReferenceFile, right: ReferenceFile) -> bool:
    return left.path == right.path and left.sha256 == right.sha256


def validate_manifest_paths(manifest: ReferenceManifest, root: Path) -> list[str]:
    missing: list[str] = []
    for entry in manifest.files:
        if not (root / entry.path).exists():
            missing.append(entry.path)
    return missing
