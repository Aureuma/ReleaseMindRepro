from pathlib import Path
from typing import Any
from releasemind_repro.config import load_config


def _write_toml(path: Path, values: dict[str, Any]) -> None:
    lines: list[str] = []
    for key, value in values.items():
        if isinstance(value, str):
            lines.append(f'{key} = "{value}"')
        elif isinstance(value, bool):
            lines.append(f"{key} = {'true' if value else 'false'}")
        else:
            lines.append(f"{key} = {value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_load_config_resolves_repository_root(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / "src" / "releasemind_repro").mkdir(parents=True)
    (repo_root / "configs").mkdir()
    (repo_root / "pyproject.toml").write_text("[project]\nname = 'tmp'\nversion = '0.0.1'\n", encoding="utf-8")

    config_path = repo_root / "configs" / "paper.toml"
    _write_toml(
        config_path,
        {
            "sample_size": 10,
            "seed": 42,
            "audit_frac": 0.5,
            "smartnote_dataset": "data/fixtures/smartnote_small.parquet",
            "rnsum_dataset": "data/fixtures/rnsum_small.jsonl",
        },
    )

    cfg = load_config(config_path)
    assert cfg.root == repo_root
    assert cfg.source_path == config_path
    assert cfg.smartnote_dataset == repo_root / "data" / "fixtures" / "smartnote_small.parquet"


def test_merge_preserves_source_path(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / "src" / "releasemind_repro").mkdir(parents=True)
    (repo_root / "configs").mkdir()
    (repo_root / "pyproject.toml").write_text("[project]\nname = 'tmp'\nversion = '0.0.1'\n", encoding="utf-8")

    config_path = repo_root / "configs" / "paper.toml"
    _write_toml(config_path, {"sample_size": 12, "seed": 1, "audit_frac": 0.5})

    cfg = load_config(config_path)
    merged = cfg.merge({"sample_size": 7})
    assert merged.source_path == config_path
    assert merged.sample_size == 7
