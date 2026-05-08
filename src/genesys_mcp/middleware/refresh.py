"""Refresh-on-401 middleware. Genesys SDK integration follows in M2."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from genesys_mcp.logging_setup import get_logger

DEFAULT_REFRESH_TIMEOUT = 10.0


class AuthExpiredError(Exception):
    """Raised by callees to signal that an access token must be refreshed."""


class RefreshError(Exception):
    """Raised when a refresh has been attempted but the call still fails."""


async def with_refresh[T](
    func: Callable[[], Awaitable[T]],
    refresh_token: Callable[[], Awaitable[None]],
    *,
    refresh_timeout: float = DEFAULT_REFRESH_TIMEOUT,
) -> T:
    """Invoke ``func``; if it raises :class:`AuthExpiredError`, refresh and retry once.

    A second ``AuthExpiredError`` from the same call escalates to
    :class:`RefreshError` so callers do not loop forever on bad credentials.
    The refresh itself is bounded by ``refresh_timeout`` seconds — a hung IdP
    must not block the request indefinitely. On timeout, ``RefreshError`` is
    raised and the original call is **not** retried.
    """
    log = get_logger(component="refresh")

    try:
        return await func()
    except AuthExpiredError:
        log.info("auth_expired_refreshing")

    try:
        await asyncio.wait_for(refresh_token(), timeout=refresh_timeout)
    except TimeoutError as exc:
        log.warning("refresh_timed_out", timeout_seconds=refresh_timeout)
        raise RefreshError(
            f"refresh timed out after {refresh_timeout}s"
        ) from exc

    try:
        return await func()
    except AuthExpiredError as exc:
        log.warning("refresh_failed_double_401")
        raise RefreshError("call still unauthorized after refresh") from exc
