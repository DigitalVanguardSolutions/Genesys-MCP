"""OpenTelemetry tracing setup — console exporter by default, OTLP if configured."""

from __future__ import annotations

import contextlib
import sys
from collections.abc import Iterator

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
)
from opentelemetry.trace import Tracer

from genesys_mcp.logging_setup import get_logger


def configure_tracing(
    *,
    transport: str = "stdio",
    service_name: str = "genesys-mcp",
    service_version: str | None = None,
    otlp_endpoint: str | None = None,
) -> TracerProvider:
    """Install a TracerProvider, picking exporters that are safe for the transport.

    Stdio MCP traffic is JSON-RPC framed on stdout, so any span exporter that
    writes to stdout would corrupt the protocol. Under ``transport="stdio"`` we
    suppress the console exporter entirely and emit a structured log noting
    that. For any other transport we attach a stderr-bound
    :class:`ConsoleSpanExporter` wrapped in :class:`BatchSpanProcessor`.

    The OTLP exporter is imported lazily so the public package does not pull
    in gRPC/HTTP exporter dependencies unless they are actually requested.
    """
    attributes: dict[str, str] = {"service.name": service_name}
    if service_version:
        attributes["service.version"] = service_version
    resource = Resource.create(attributes)

    provider = TracerProvider(resource=resource)
    log = get_logger(component="tracing")

    if transport == "stdio":
        log.info("tracing_console_exporter_suppressed", reason="stdio transport")
    else:
        provider.add_span_processor(
            BatchSpanProcessor(ConsoleSpanExporter(out=sys.stderr))
        )

    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (  # type: ignore[import-not-found]
                OTLPSpanExporter,
            )
        except ImportError:  # pragma: no cover - depends on optional extra
            pass
        else:
            provider.add_span_processor(
                BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint))
            )

    trace.set_tracer_provider(provider)
    return provider


def get_tracer(name: str = "genesys_mcp") -> Tracer:
    """Return a tracer rooted at the configured provider."""
    return trace.get_tracer(name)


@contextlib.contextmanager
def tool_span(tool_name: str) -> Iterator[None]:
    """Context manager that wraps a tool invocation in a span."""
    tracer = get_tracer()
    with tracer.start_as_current_span(f"tool.{tool_name}"):
        yield


__all__ = ["configure_tracing", "get_tracer", "tool_span"]
