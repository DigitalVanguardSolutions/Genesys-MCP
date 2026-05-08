"""FastMCP server factory and runtime entry points."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from mcp.server.fastmcp import FastMCP

from genesys_mcp import __version__
from genesys_mcp.config import Settings
from genesys_mcp.license import License, load_license
from genesys_mcp.logging_setup import get_logger
from genesys_mcp.registry import (
    PluginContext,
    PluginLoadResult,
    load_plugins,
    register_plugins,
)

SERVER_NAME = "genesys-mcp"
FastMCPTransport = Literal["stdio", "sse", "streamable-http"]


@dataclass
class ServerApp:
    """A constructed Genesys MCP application: settings, license, server, plugins.

    Holding the application as an explicit object (rather than module globals)
    is what lets us run multiple instances per process — important for tests
    and for the future hosted multi-tenant gateway.
    """

    settings: Settings
    license: License
    server: FastMCP
    plugins: PluginLoadResult = field(default_factory=PluginLoadResult)


def create_server(
    settings: Settings | None = None,
    license: License | None = None,
    *,
    load_plugins_from_entry_points: bool = True,
) -> ServerApp:
    """Build a fully wired :class:`ServerApp` ready to be ``run``.

    The caller is responsible for installing logging and tracing **once per
    process** before calling this function (see :func:`genesys_mcp.cli.main`).
    Multiple ``ServerApp`` instances may be created in a single process — for
    tests, or for the future multi-tenant gateway — and they all share the
    process-wide tracer and logger as OpenTelemetry and structlog intend.

    Parameters
    ----------
    settings:
        Settings instance to use. If ``None``, one is constructed from the
        environment (the standard production path).
    license:
        License implementation. If ``None``, the active license is resolved
        from the ``genesys_mcp.license`` entry-point group, falling back to
        :class:`genesys_mcp.license.NoOpLicense`.
    load_plugins_from_entry_points:
        When ``False``, no plugins are discovered. Useful for tests that want
        to register tools manually against ``app.server``.
    """
    cfg = settings or Settings()
    lic = license if license is not None else load_license()

    server = FastMCP(
        name=SERVER_NAME,
        instructions=(
            "Genesys MCP — vendor-neutral access to Genesys Cloud. "
            "Tools land in v0.2; this build exposes the framework only."
        ),
        host=cfg.host,
        port=cfg.port,
        log_level=cfg.log_level,
    )

    log = get_logger(component="server")

    plugins = (
        load_plugins() if load_plugins_from_entry_points else PluginLoadResult()
    )
    if plugins.loaded:
        ctx = PluginContext(server=server, settings=cfg, license=lic)
        register_plugins(ctx, plugins)
    if plugins.errors:
        log.warning("plugin_errors", errors=plugins.errors)

    log.info(
        "server_initialized",
        version=__version__,
        license=lic.describe(),
        transport=cfg.transport,
        host=cfg.host if cfg.transport == "http" else None,
        port=cfg.port if cfg.transport == "http" else None,
        plugin_count=plugins.count,
        plugin_errors=len(plugins.errors),
        enable_writes=cfg.enable_writes,
    )

    return ServerApp(settings=cfg, license=lic, server=server, plugins=plugins)


def run_app(app: ServerApp) -> None:
    """Run the application on the configured transport, blocking until exit."""
    log = get_logger(component="server")
    transport = app.settings.transport
    fastmcp_transport: FastMCPTransport = (
        "streamable-http" if transport == "http" else "stdio"
    )

    log.info("server_starting", transport=transport, fastmcp_transport=fastmcp_transport)
    try:
        app.server.run(transport=fastmcp_transport)
    finally:
        log.info("server_shutdown")


__all__ = ["SERVER_NAME", "ServerApp", "create_server", "run_app"]
