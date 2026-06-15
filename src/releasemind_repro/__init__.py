"""ReleaseMind reproducibility package."""

from importlib.metadata import version
from pathlib import Path
import tomllib


def _project_version() -> str:
    try:
        return version("releasemind-repro")
    except Exception:
        pass

    try:
        project_root = Path(__file__).resolve().parents[2]
        project_toml = project_root / "pyproject.toml"
        if project_toml.exists():
            data = tomllib.loads(project_toml.read_text(encoding="utf-8"))
            return str(data.get("project", {}).get("version", "0.0.0"))
    except Exception:
        pass

    return "0.0.0"


__all__ = [
    "__version__",
]

__version__ = _project_version()
