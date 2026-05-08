"""Shared pytest fixtures for the Genesys MCP test suite."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from genesys_mcp.config import Settings
from genesys_mcp.license import License, NoOpLicense
from genesys_mcp.logging_setup import clear_request_id, configure_logging
from genesys_mcp.server import ServerApp, create_server
from genesys_mcp.tracing import configure_tracing


def make_settings(**overrides: Any) -> Settings:
    """Construct a Settings instance with no .env file bleed-through."""
    return Settings(_env_file=None, **overrides)  # type: ignore[call-arg]


@pytest.fixture(scope="session", autouse=True)
def _configure_logging_and_tracing_once() -> None:
    """Install logging + tracing exactly once for the whole test session.

    Production `cli.main()` does this once per process before any
    `create_server()` runs. Tests bypass `cli.main()`, so this fixture
    stands in for that one-time setup.
    """
    configure_logging("DEBUG", force_json=True)
    configure_tracing(transport="stdio", service_name="genesys-mcp-tests")


@pytest.fixture(autouse=True)
def _reset_request_id() -> Iterator[None]:
    """Make sure no test leaks a request id into another."""
    yield
    clear_request_id()


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Settings with a clean environment — no host .env bleed-through."""
    for var in (
        "MCP_TRANSPORT",
        "MCP_HOST",
        "MCP_PORT",
        "LOG_LEVEL",
        "GENESYS_MCP_ENABLE_WRITES",
        "GENESYS_REGION",
        "GENESYS_CLIENT_ID",
        "GENESYS_CLIENT_SECRET",
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "OTEL_SERVICE_NAME",
    ):
        monkeypatch.delenv(var, raising=False)
    return make_settings()


@pytest.fixture
def mock_license() -> License:
    """A License that permits everything — same as the default."""
    return NoOpLicense()


@pytest.fixture
def server_app(settings: Settings, mock_license: License) -> ServerApp:
    """A constructed ServerApp with no plugins loaded — safe for unit tests."""
    return create_server(
        settings=settings,
        license=mock_license,
        load_plugins_from_entry_points=False,
    )
