"""Command-line entry point for the Genesys MCP server."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from pydantic import ValidationError

from genesys_mcp import __version__
from genesys_mcp.config import Settings
from genesys_mcp.logging_setup import configure_logging, get_logger
from genesys_mcp.server import create_server, run_app
from genesys_mcp.tracing import configure_tracing


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="genesys-mcp",
        description=(
            "Vendor-neutral Model Context Protocol server for Genesys Cloud. "
            "Reads configuration from the environment; CLI flags override env."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "http"),
        default=None,
        help="Transport to bind. Defaults to MCP_TRANSPORT (stdio).",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="HTTP bind host. Only used with --transport http. Defaults to MCP_HOST.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="HTTP bind port. Only used with --transport http. Defaults to MCP_PORT.",
    )
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        default=None,
        help="Override LOG_LEVEL.",
    )
    parser.add_argument(
        "--enable-writes",
        action="store_true",
        default=None,
        help=(
            "Enable the curated low-blast-radius write tools "
            "(presence.set, conversations.add_note, conversations.set_wrapup_code). "
            "Default is read-only."
        ),
    )
    return parser


def _settings_from_args(args: argparse.Namespace) -> Settings:
    """Construct Settings from environment, then apply CLI overrides."""
    base = Settings()
    overrides: dict[str, object] = {}
    if args.transport is not None:
        overrides["transport"] = args.transport
    if args.host is not None:
        overrides["host"] = args.host
    if args.port is not None:
        overrides["port"] = args.port
    if args.log_level is not None:
        overrides["log_level"] = args.log_level
    if args.enable_writes:
        overrides["enable_writes"] = True
    if not overrides:
        return base
    return base.model_copy(update=overrides)


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point used by both the console script and ``python -m genesys_mcp``."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        settings = _settings_from_args(args)
    except ValidationError as exc:
        configure_logging("ERROR")
        get_logger(component="cli").error("settings_invalid", errors=exc.errors())
        return 2

    configure_logging(settings.log_level)
    configure_tracing(
        transport=settings.transport,
        service_name=settings.otel_service_name,
        service_version=__version__,
        otlp_endpoint=settings.otel_endpoint,
    )

    log = get_logger(component="cli")
    try:
        app = create_server(settings=settings)
        run_app(app)
    except KeyboardInterrupt:
        log.info("shutdown_keyboard_interrupt")
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
