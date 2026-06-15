from releasemind_repro import __version__
from releasemind_repro.cli import _build_parser, _normalize_argv


def test_version_is_semver_like() -> None:
    assert isinstance(__version__, str)
    assert __version__
    parts = __version__.split(".")
    assert len(parts) >= 3


def test_normalize_argv_moves_config_before_subcommand() -> None:
    normalized = _normalize_argv(["train-proxies", "--config", "configs/paper_smoke.toml", "--json"])
    parser = _build_parser()
    args = parser.parse_args(normalized)
    assert args.command == "train-proxies"
    assert args.config == "configs/paper_smoke.toml"


def test_normalize_argv_supports_inline_config_flag() -> None:
    parser = _build_parser()
    args = parser.parse_args(_normalize_argv(["--config=configs/paper_smoke.toml", "doctor"]))
    assert args.command == "doctor"
    assert args.config == "configs/paper_smoke.toml"


def test_normalize_argv_passes_unknown_command_errors() -> None:
    parser = _build_parser()
    try:
        parser.parse_args(_normalize_argv(["--config", "configs/paper_smoke.toml", "not-a-command"]))
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("Expected parser to reject unknown commands")
