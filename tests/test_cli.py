"""CLI parsing and dry-boot smoke tests."""

from __future__ import annotations

import pytest

from genesys_mcp import cli as cli_mod


def test_help_exits_cleanly(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli_mod.main(["--help"])
    assert excinfo.value.code == 0

    out = capsys.readouterr().out
    assert "--transport" in out
    assert "--host" in out
    assert "--port" in out
    assert "--enable-writes" in out


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli_mod.main(["--version"])
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert "genesys-mcp" in out


def test_settings_overrides_from_args(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("MCP_TRANSPORT", "MCP_HOST", "MCP_PORT", "LOG_LEVEL"):
        monkeypatch.delenv(var, raising=False)

    parser = cli_mod._build_parser()
    args = parser.parse_args(
        [
            "--transport",
            "http",
            "--host",
            "0.0.0.0",
            "--port",
            "18000",
            "--log-level",
            "WARNING",
            "--enable-writes",
        ]
    )
    settings = cli_mod._settings_from_args(args)
    assert settings.transport == "http"
    assert settings.host == "0.0.0.0"
    assert settings.port == 18000
    assert settings.log_level == "WARNING"
    assert settings.enable_writes is True


def test_settings_no_overrides_returns_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_TRANSPORT", "stdio")
    monkeypatch.setenv("MCP_PORT", "8123")
    parser = cli_mod._build_parser()
    args = parser.parse_args([])
    settings = cli_mod._settings_from_args(args)
    assert settings.transport == "stdio"
    assert settings.port == 8123


def test_main_invokes_run_app(monkeypatch: pytest.MonkeyPatch) -> None:
    """End-to-end: main() builds an app and calls run_app on it."""
    captured: dict[str, object] = {}

    def _fake_run_app(app: object) -> None:
        captured["app"] = app

    monkeypatch.setenv("MCP_TRANSPORT", "stdio")
    monkeypatch.setattr(cli_mod, "run_app", _fake_run_app)

    rc = cli_mod.main([])
    assert rc == 0
    assert "app" in captured
