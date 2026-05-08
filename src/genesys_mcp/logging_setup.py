"""Structured logging configuration for the Genesys MCP server."""

from __future__ import annotations

import logging
import re
import sys
from contextvars import ContextVar
from typing import Any
from uuid import uuid4

import structlog
from structlog.types import EventDict, Processor, WrappedLogger

_request_id_var: ContextVar[str | None] = ContextVar("genesys_mcp_request_id", default=None)

_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def new_request_id() -> str:
    """Generate a fresh request id and bind it to the current context."""
    rid = uuid4().hex
    _request_id_var.set(rid)
    return rid


def set_request_id(request_id: str | None) -> None:
    """Bind an externally supplied request id to the current context.

    Validates against ``[A-Za-z0-9_-]{1,64}``; raises :class:`ValueError` for
    anything else (whitespace, control characters, empty string, oversize).
    Passing ``None`` clears the id.
    """
    if request_id is not None and not _REQUEST_ID_PATTERN.match(request_id):
        raise ValueError(
            "request_id must match [A-Za-z0-9_-]{1,64}"
        )
    _request_id_var.set(request_id)


def get_request_id() -> str | None:
    """Return the current request id, if one has been bound."""
    return _request_id_var.get()


def clear_request_id() -> None:
    """Drop the request id from the current context."""
    _request_id_var.set(None)


def _inject_request_id(
    _logger: WrappedLogger,
    _method_name: str,
    event_dict: EventDict,
) -> EventDict:
    rid = _request_id_var.get()
    if rid is not None and "request_id" not in event_dict:
        event_dict["request_id"] = rid
    return event_dict


def configure_logging(level: str = "INFO", *, force_json: bool | None = None) -> None:
    """Configure ``structlog`` to emit either pretty or JSON output to stderr.

    Output is JSON unless stderr is a TTY (developer ergonomics) or the caller
    explicitly forces a renderer via ``force_json``.
    """
    structlog.reset_defaults()

    is_tty = sys.stderr.isatty()
    use_json = force_json if force_json is not None else not is_tty

    renderer: Processor
    if use_json:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=is_tty)

    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        _inject_request_id,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        renderer,
    ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(level)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )


def get_logger(**initial_values: Any) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger pre-bound with the supplied context."""
    log: structlog.stdlib.BoundLogger = structlog.get_logger().bind(**initial_values)
    return log


__all__ = [
    "clear_request_id",
    "configure_logging",
    "get_logger",
    "get_request_id",
    "new_request_id",
    "set_request_id",
]
