"""Retry middleware: 429 honours Retry-After; otherwise exponential backoff."""

from __future__ import annotations

import datetime as dt

import pytest

from genesys_mcp.middleware.retry import (
    RateLimitError,
    _backoff_delay,
    parse_retry_after,
    with_retry,
)


def test_parse_retry_after_seconds() -> None:
    assert parse_retry_after("30") == 30.0
    assert parse_retry_after("0") == 0.0
    assert parse_retry_after("  5  ") == 5.0


def test_parse_retry_after_negative_clamped() -> None:
    assert parse_retry_after("-5") == 0.0


def test_parse_retry_after_http_date_future() -> None:
    future = dt.datetime.now(tz=dt.UTC) + dt.timedelta(seconds=42)
    header = future.strftime("%a, %d %b %Y %H:%M:%S GMT")
    parsed = parse_retry_after(header)
    assert parsed is not None
    assert 30 <= parsed <= 60


def test_parse_retry_after_invalid() -> None:
    assert parse_retry_after(None) is None
    assert parse_retry_after("") is None
    assert parse_retry_after("not-a-thing") is None


async def test_with_retry_succeeds_first_try() -> None:
    calls = {"n": 0}

    async def fn() -> str:
        calls["n"] += 1
        return "ok"

    result = await with_retry(fn, max_attempts=3)
    assert result == "ok"
    assert calls["n"] == 1


async def test_with_retry_honours_retry_after() -> None:
    sleeps: list[float] = []

    async def sleeper(delay: float) -> None:
        sleeps.append(delay)

    calls = {"n": 0}

    async def fn() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise RateLimitError("slow down", retry_after=7.5)
        return "ok"

    result = await with_retry(fn, max_attempts=5, sleep=sleeper)
    assert result == "ok"
    assert calls["n"] == 3
    assert sleeps == [7.5, 7.5]


async def test_with_retry_caps_retry_after_at_max_delay() -> None:
    sleeps: list[float] = []

    async def sleeper(delay: float) -> None:
        sleeps.append(delay)

    calls = {"n": 0}

    async def fn() -> str:
        calls["n"] += 1
        if calls["n"] < 2:
            raise RateLimitError(retry_after=999.0)
        return "ok"

    await with_retry(fn, max_attempts=3, max_delay=10.0, sleep=sleeper)
    assert sleeps == [10.0]


async def test_with_retry_exponential_backoff_when_no_header() -> None:
    sleeps: list[float] = []

    async def sleeper(delay: float) -> None:
        sleeps.append(delay)

    calls = {"n": 0}

    async def fn() -> str:
        calls["n"] += 1
        if calls["n"] < 4:
            raise RateLimitError()
        return "ok"

    await with_retry(
        fn, max_attempts=5, base_delay=1.0, max_delay=8.0, sleep=sleeper
    )
    assert len(sleeps) == 3
    assert all(d >= 1.0 for d in sleeps)
    assert all(d <= 8.0 for d in sleeps)


async def test_with_retry_gives_up_after_max_attempts() -> None:
    async def sleeper(delay: float) -> None:
        return None

    calls = {"n": 0}

    async def fn() -> str:
        calls["n"] += 1
        raise RateLimitError("nope")

    with pytest.raises(RateLimitError):
        await with_retry(fn, max_attempts=3, sleep=sleeper)
    assert calls["n"] == 3


async def test_with_retry_does_not_swallow_other_errors() -> None:
    async def fn() -> str:
        raise ValueError("not a rate limit")

    with pytest.raises(ValueError, match="not a rate limit"):
        await with_retry(fn, max_attempts=5)


async def test_with_retry_rejects_zero_attempts() -> None:
    async def fn() -> str:
        return "x"

    with pytest.raises(ValueError):
        await with_retry(fn, max_attempts=0)


def test_backoff_delay_never_exceeds_max_delay() -> None:
    """Property: across many random samples, delay never exceeds max_delay."""
    max_delay = 8.0
    base_delay = 1.0
    for attempt in range(1, 11):
        for _ in range(50):
            delay = _backoff_delay(attempt, base_delay, max_delay)
            assert base_delay <= delay <= max_delay


async def test_with_retry_backoff_path_respects_max_delay() -> None:
    sleeps: list[float] = []

    async def sleeper(delay: float) -> None:
        sleeps.append(delay)

    calls = {"n": 0}
    max_delay = 4.0

    async def fn() -> str:
        calls["n"] += 1
        if calls["n"] < 6:
            raise RateLimitError()
        return "ok"

    await with_retry(
        fn, max_attempts=10, base_delay=1.0, max_delay=max_delay, sleep=sleeper
    )
    assert all(d <= max_delay for d in sleeps)
