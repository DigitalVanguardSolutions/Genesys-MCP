"""Plugin registry — discovers and registers tools/resources/prompts via entry points."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from importlib.metadata import EntryPoint, entry_points
from typing import Protocol, runtime_checkable

from mcp.server.fastmcp import FastMCP

from genesys_mcp.config import Settings
from genesys_mcp.license import License
from genesys_mcp.logging_setup import get_logger

PLUGIN_ENTRY_POINT_GROUP = "genesys_mcp.plugins"


@dataclass(frozen=True)
class PluginContext:
    """Everything a plugin needs to register itself with the server.

    Frozen on purpose — this is the public contract between the server and
    plugins. Adding new fields is a non-breaking change as long as defaults
    are supplied; mutating one would silently re-shape every plugin's view of
    the world.
    """

    server: FastMCP
    settings: Settings
    license: License


PluginRegisterFn = Callable[[PluginContext], None]


@runtime_checkable
class Plugin(Protocol):
    """A plugin contributes tools, resources, or prompts to a FastMCP server."""

    def register(self, ctx: PluginContext) -> None:
        """Attach this plugin's surface (tools/resources/prompts) to the server."""


@dataclass(frozen=True)
class LoadedPlugin:
    """Metadata about a plugin that was successfully loaded."""

    name: str
    register: PluginRegisterFn


@dataclass
class PluginLoadResult:
    """Outcome of attempting to load all plugins from the entry-point group."""

    loaded: list[LoadedPlugin] = field(default_factory=list)
    errors: list[tuple[str, str]] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.loaded)


def _resolve_register(target: object) -> PluginRegisterFn | None:
    """Coerce a loaded entry-point target into a ``register(ctx)`` callable."""
    register = getattr(target, "register", None)
    if callable(register):
        return register  # type: ignore[no-any-return]
    if callable(target):
        return target
    return None


def discover_plugins(
    *, group: str = PLUGIN_ENTRY_POINT_GROUP
) -> Iterable[EntryPoint]:
    """Yield every entry point declared under the given group."""
    yield from entry_points(group=group)


def load_plugins(
    *, group: str = PLUGIN_ENTRY_POINT_GROUP
) -> PluginLoadResult:
    """Load all plugin entry points without yet attaching them to a server.

    Failures (import errors, bad targets) are collected into ``errors`` rather
    than raised — a single broken plugin must not bring down the whole server.
    """
    log = get_logger(component="registry", group=group)
    result = PluginLoadResult()

    for ep in discover_plugins(group=group):
        try:
            target = ep.load()
        except Exception as exc:
            log.warning("plugin_load_failed", plugin=ep.name, error=str(exc))
            result.errors.append((ep.name, str(exc)))
            continue

        register = _resolve_register(target)
        if register is None:
            log.warning("plugin_invalid_target", plugin=ep.name)
            result.errors.append((ep.name, "target is not a Plugin or callable"))
            continue

        result.loaded.append(LoadedPlugin(name=ep.name, register=register))

    log.info("plugins_loaded", count=result.count, errors=len(result.errors))
    return result


def register_plugins(ctx: PluginContext, plugins: PluginLoadResult) -> None:
    """Attach every successfully-loaded plugin to a FastMCP server.

    A registration failure for one plugin does not abort registration of the
    others. Errors are appended to ``plugins.errors`` so the caller can surface
    them.
    """
    log = get_logger(component="registry")
    for plugin in plugins.loaded:
        try:
            plugin.register(ctx)
        except Exception as exc:
            log.warning("plugin_register_failed", plugin=plugin.name, error=str(exc))
            plugins.errors.append((plugin.name, f"register failed: {exc}"))
            continue
        log.info("plugin_registered", plugin=plugin.name)


__all__ = [
    "PLUGIN_ENTRY_POINT_GROUP",
    "LoadedPlugin",
    "Plugin",
    "PluginContext",
    "PluginLoadResult",
    "PluginRegisterFn",
    "discover_plugins",
    "load_plugins",
    "register_plugins",
]
