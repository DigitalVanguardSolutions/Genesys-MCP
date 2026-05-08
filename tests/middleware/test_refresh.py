"""Refresh middleware: refresh on 401, escalate on double-401."""

from __future__ import annotations

import asyncio

import pytest

from genesys_mcp.middleware.refresh import AuthExpiredError, RefreshError, with_refresh


async def test_succeeds_without_refresh() -> None:
    refreshes = {"n": 0}

    async def refresh() -> None:
        refreshes["n"] += 1

    async def call() -> str:
        return "ok"

    result = await with_refresh(call, refresh)
    assert result == "ok"
    assert refreshes["n"] == 0


async def test_refreshes_on_401_and_retries() -> None:
    refreshes = {"n": 0}
    calls = {"n": 0}

    async def refresh() -> None:
        refreshes["n"] += 1

    async def call() -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            raise AuthExpiredError("expired")
        return "ok"

    result = await with_refresh(call, refresh)
    assert result == "ok"
    assert refreshes["n"] == 1
    assert calls["n"] == 2


async def test_double_401_escalates_to_refresh_error() -> None:
    refreshes = {"n": 0}

    async def refresh() -> None:
        refreshes["n"] += 1

    async def call() -> str:
        raise AuthExpiredError("still expired")

    with pytest.raises(RefreshError):
        await with_refresh(call, refresh)
    assert refreshes["n"] == 1


async def test_passes_through_unrelated_errors() -> None:
    async def refresh() -> None:
        return None

    async def call() -> str:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await with_refresh(call, refresh)


async def test_refresh_timeout_raises_refresh_error_without_retry() -> None:
    """A hung refresh must abort within the timeout and skip the retry call."""
    calls = {"n": 0}

    async def refresh() -> None:
        await asyncio.sleep(0.5)

    async def call() -> str:
        calls["n"] += 1
        raise AuthExpiredError("expired")

    with pytest.raises(RefreshError, match="timed out"):
        await with_refresh(call, refresh, refresh_timeout=0.05)

    # The first call (which raised AuthExpiredError) ran, but the post-refresh
    # retry must NOT have run because the refresh itself timed out.
    assert calls["n"] == 1


async def test_refresh_timeout_passes_when_refresh_is_fast() -> None:
    refreshes = {"n": 0}
    calls = {"n": 0}

    async def refresh() -> None:
        refreshes["n"] += 1

    async def call() -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            raise AuthExpiredError("expired")
        return "ok"

    result = await with_refresh(call, refresh, refresh_timeout=1.0)
    assert result == "ok"
    assert refreshes["n"] == 1
    assert calls["n"] == 2
