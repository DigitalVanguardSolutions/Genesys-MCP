"""Tracing setup must never write spans to stdout under stdio transport."""

from __future__ import annotations

import sys

from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
)

from genesys_mcp import tracing as tracing_mod


def _processors(provider: object) -> list[object]:
    """Return the list of installed span processors on a TracerProvider."""
    multi = provider._active_span_processor  # type: ignore[attr-defined]
    return list(getattr(multi, "_span_processors", ()))


def _console_exporters(processors: list[object]) -> list[ConsoleSpanExporter]:
    found: list[ConsoleSpanExporter] = []
    for proc in processors:
        exporter = getattr(proc, "span_exporter", None)
        if isinstance(exporter, ConsoleSpanExporter):
            found.append(exporter)
    return found


def test_stdio_transport_installs_no_console_exporter() -> None:
    """Under stdio, any stdout writer would corrupt JSON-RPC framing."""
    provider = tracing_mod.configure_tracing(transport="stdio")
    processors = _processors(provider)
    assert _console_exporters(processors) == []


def test_http_transport_installs_stderr_console_exporter_via_batch_processor() -> None:
    provider = tracing_mod.configure_tracing(transport="http")
    processors = _processors(provider)
    consoles = _console_exporters(processors)

    assert len(consoles) == 1, "http transport must install exactly one console exporter"

    # The exporter must write to stderr, never stdout.
    exporter = consoles[0]
    out_stream = getattr(exporter, "out", None)
    assert out_stream is sys.stderr

    # And it must be wrapped in BatchSpanProcessor — no SimpleSpanProcessor in
    # production paths (it serialises export, blocking the request thread).
    matched_proc = None
    for proc in processors:
        if getattr(proc, "span_exporter", None) is exporter:
            matched_proc = proc
            break
    assert matched_proc is not None
    assert isinstance(matched_proc, BatchSpanProcessor)
