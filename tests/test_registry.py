"""Plugin loader: empty registry boots; mock entry-point registers a tool."""

from __future__ import annotations

from typing import Any

import pytest
from mcp.server.fastmcp import FastMCP

from genesys_mcp import registry as registry_mod
from genesys_mcp.config import Settings
from genesys_mcp.license import NoOpLicense
from genesys_mcp.registry import (
    PLUGIN_ENTRY_POINT_GROUP,
    LoadedPlugin,
    PluginContext,
    PluginLoadResult,
    load_plugins,
    register_plugins,
)
from tests.conftest import make_settings


def _make_ctx(settings: Settings | None = None) -> PluginContext:
    return PluginContext(
        server=FastMCP(name="test"),
        settings=settings or make_settings(),
        license=NoOpLicense(),
    )


class _FakeEntryPoint:
    def __init__(self, name: str, target: Any, *, raises: Exception | None = None):
        self.name = name
        self._target = target
        self._raises = raises

    def load(self) -> Any:
        if self._raises:
            raise self._raises
        return self._target


def test_empty_registry_loads(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(registry_mod, "entry_points", lambda group: [])
    result = load_plugins()
    assert result.count == 0
    assert result.errors == []


def test_callable_entry_point_loads(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[PluginContext] = []

    def _register(ctx: PluginContext) -> None:
        seen.append(ctx)

    monkeypatch.setattr(
        registry_mod,
        "entry_points",
        lambda group: [_FakeEntryPoint("noop", _register)],
    )
    result = load_plugins()
    assert result.count == 1
    assert result.errors == []

    ctx = _make_ctx()
    register_plugins(ctx, result)
    assert seen == [ctx]


def test_plugin_object_with_register(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Plugin:
        def __init__(self) -> None:
            self.calls = 0
            self.last_ctx: PluginContext | None = None

        def register(self, ctx: PluginContext) -> None:
            self.calls += 1
            self.last_ctx = ctx

    plugin = _Plugin()
    monkeypatch.setattr(
        registry_mod,
        "entry_points",
        lambda group: [_FakeEntryPoint("plug", plugin)],
    )
    result = load_plugins()
    assert result.count == 1

    ctx = _make_ctx()
    register_plugins(ctx, result)
    assert plugin.calls == 1
    assert plugin.last_ctx is ctx


def test_load_failure_collected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        registry_mod,
        "entry_points",
        lambda group: [
            _FakeEntryPoint("broken", None, raises=ImportError("nope")),
        ],
    )
    result = load_plugins()
    assert result.count == 0
    assert len(result.errors) == 1
    assert result.errors[0][0] == "broken"


def test_register_failure_collected() -> None:
    def _bad_register(ctx: PluginContext) -> None:
        raise RuntimeError("plugin exploded")

    plugins = PluginLoadResult(
        loaded=[LoadedPlugin(name="bad", register=_bad_register)],
    )
    register_plugins(_make_ctx(), plugins)
    assert plugins.errors == [("bad", "register failed: plugin exploded")]


def test_real_entry_point_call_does_not_raise() -> None:
    result = load_plugins(group=PLUGIN_ENTRY_POINT_GROUP)
    assert result.count >= 0
