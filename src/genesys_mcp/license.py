"""License hook — no-op default that the Pro package replaces via entry point."""

from __future__ import annotations

from importlib.metadata import entry_points
from typing import Protocol, runtime_checkable

LICENSE_ENTRY_POINT_GROUP = "genesys_mcp.license"

__all__ = [
    "LICENSE_ENTRY_POINT_GROUP",
    "License",
    "NoOpLicense",
    "load_license",
]


@runtime_checkable
class License(Protocol):
    """A pluggable license check.

    The public package ships a no-op implementation that permits everything.
    The Pro package registers a real validator under the
    `genesys_mcp.license` entry-point group; the first registered entry wins.
    """

    def is_feature_enabled(self, feature: str) -> bool:
        """Return True if the named feature is licensed for use."""

    def describe(self) -> str:
        """Human-readable identifier for logs (e.g. ``no-op`` or ``pro:<edition>``)."""


class NoOpLicense:
    """Default License implementation. Permits every feature."""

    def is_feature_enabled(self, feature: str) -> bool:
        return True

    def describe(self) -> str:
        return "no-op"


def load_license() -> License:
    """Resolve the active License implementation.

    Loads the first entry point under ``genesys_mcp.license`` if any plugin
    has registered one (the Pro package does this); otherwise returns
    :class:`NoOpLicense`. Bad entry points are skipped so a broken plugin
    cannot brick the server.
    """
    for ep in entry_points(group=LICENSE_ENTRY_POINT_GROUP):
        try:
            factory = ep.load()
        except Exception:
            continue
        try:
            candidate = factory() if callable(factory) else factory
        except Exception:
            continue
        if isinstance(candidate, License):
            return candidate
    return NoOpLicense()
