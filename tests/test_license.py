"""License hook — no-op default and entry-point replacement contract."""

from __future__ import annotations

from importlib.metadata import EntryPoint
from typing import Any

import pytest

from genesys_mcp import license as license_mod
from genesys_mcp.license import License, NoOpLicense, load_license


def test_noop_license_permits_everything() -> None:
    lic = NoOpLicense()
    assert lic.is_feature_enabled("writes") is True
    assert lic.is_feature_enabled("anything-at-all") is True
    assert lic.describe() == "no-op"


def test_load_license_default_is_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(license_mod, "entry_points", lambda group: [])
    lic = load_license()
    assert isinstance(lic, NoOpLicense)


class _ProLicense:
    def is_feature_enabled(self, feature: str) -> bool:
        return False

    def describe(self) -> str:
        return "pro:test"


def test_load_license_picks_up_entry_point(monkeypatch: pytest.MonkeyPatch) -> None:
    pro: License = _ProLicense()

    class _FakeEP:
        name = "pro"

        def load(self) -> Any:
            return lambda: pro

    monkeypatch.setattr(license_mod, "entry_points", lambda group: [_FakeEP()])
    lic = load_license()
    assert lic is pro
    assert lic.describe() == "pro:test"


def test_load_license_skips_broken_entry_point(monkeypatch: pytest.MonkeyPatch) -> None:
    class _BadEP:
        name = "broken"

        def load(self) -> Any:
            raise ImportError("no such module")

    class _GoodEP:
        name = "good"

        def load(self) -> Any:
            return _ProLicense

    monkeypatch.setattr(license_mod, "entry_points", lambda group: [_BadEP(), _GoodEP()])
    lic = load_license()
    assert isinstance(lic, _ProLicense)


def test_real_entry_points_call_does_not_raise() -> None:
    """Smoke test against the real importlib.metadata machinery."""
    for ep in license_mod.entry_points(group=license_mod.LICENSE_ENTRY_POINT_GROUP):
        assert isinstance(ep, EntryPoint)
