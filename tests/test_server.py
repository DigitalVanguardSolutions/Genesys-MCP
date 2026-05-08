"""Server factory wires settings, license, transport, and plugins together."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from genesys_mcp.config import Settings
from genesys_mcp.license import NoOpLicense
from genesys_mcp.server import SERVER_NAME, ServerApp, create_server


def test_create_server_returns_app(server_app: ServerApp) -> None:
    assert isinstance(server_app, ServerApp)
    assert isinstance(server_app.server, FastMCP)
    assert server_app.server.name == SERVER_NAME


def test_create_server_uses_provided_license(settings: Settings) -> None:
    license = NoOpLicense()
    app = create_server(
        settings=settings, license=license, load_plugins_from_entry_points=False
    )
    assert app.license is license


def test_create_server_passes_host_and_port(settings: Settings) -> None:
    overrides = settings.model_copy(update={"host": "10.0.0.1", "port": 12345})
    app = create_server(settings=overrides, load_plugins_from_entry_points=False)
    assert app.server.settings.host == "10.0.0.1"
    assert app.server.settings.port == 12345


def test_create_server_advertises_empty_tool_surface(server_app: ServerApp) -> None:
    """In M1 we expose no tools, no resources, no prompts."""
    tool_manager = server_app.server._tool_manager
    assert list(tool_manager.list_tools()) == []
