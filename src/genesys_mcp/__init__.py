"""Genesys MCP — vendor-neutral Model Context Protocol server for Genesys Cloud."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("genesys-mcp")
except PackageNotFoundError:  # pragma: no cover - only hit before install
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
