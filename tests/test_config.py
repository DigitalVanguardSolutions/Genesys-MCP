"""Settings load and validate from environment variables."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from tests.conftest import make_settings


def test_defaults_are_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in (
        "MCP_TRANSPORT",
        "MCP_HOST",
        "MCP_PORT",
        "LOG_LEVEL",
        "GENESYS_MCP_ENABLE_WRITES",
    ):
        monkeypatch.delenv(var, raising=False)
    s = make_settings()
    assert s.transport == "stdio"
    assert s.host == "127.0.0.1"
    assert s.port == 8000
    assert s.log_level == "INFO"
    assert s.enable_writes is False
    assert s.genesys_client_secret is None


def test_reads_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_TRANSPORT", "HTTP")
    monkeypatch.setenv("MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("MCP_PORT", "9001")
    monkeypatch.setenv("LOG_LEVEL", "debug")
    monkeypatch.setenv("GENESYS_MCP_ENABLE_WRITES", "true")
    monkeypatch.setenv("GENESYS_CLIENT_SECRET", "shh-secret")

    s = make_settings()
    assert s.transport == "http"
    assert s.host == "0.0.0.0"
    assert s.port == 9001
    assert s.log_level == "DEBUG"
    assert s.enable_writes is True
    assert s.genesys_client_secret is not None
    assert s.genesys_client_secret.get_secret_value() == "shh-secret"


def test_invalid_transport_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_TRANSPORT", "carrier-pigeon")
    with pytest.raises(ValidationError):
        make_settings()


def test_port_out_of_range_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_PORT", "99999")
    with pytest.raises(ValidationError):
        make_settings()


def test_settings_are_frozen(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MCP_TRANSPORT", raising=False)
    s = make_settings()
    with pytest.raises(ValidationError):
        s.transport = "http"  # type: ignore[misc]
