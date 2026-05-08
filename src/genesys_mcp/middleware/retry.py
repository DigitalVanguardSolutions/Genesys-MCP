"""429-aware retry wrapper that honours Retry-After and falls back to backoff.

The retry loop is hand-rolled because the 429 / Retry-After contract needs
custom handling (the header value drives the delay, overriding any backoff
schedule). A library like ``tenacity`` would still need a custom wait
strategy, so we keep a single small implementation in tree.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import random
from collections.abc import Awaitable, Callable
from email.utils import parsedate_to_datetime

from genesys_mcp.logging_setup import get_logger

DEFAULT_MAX_ATTEMPTS = 5
DEFAULT_BASE_DELAY = 1.0
DEFAULT_MAX_DELAY = 30.0


class RateLimitError(Exception):
    """Raised when an upstream call returns a 429 Too Many Requests.

    The optional ``retry_after`` value (seconds, parsed from the response
    header) tells :func:`with_retry` how long to wait before retrying.
    """

    def __init__(self, message: str = "rate limited", retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


def parse_retry_after(value: str | None) -> float | None:
    """Parse a ``Retry-After`` header value into seconds.

    Accepts either a delta-seconds integer (`"30"`) or an HTTP-date
    (`"Fri, 31 Dec 2026 23:59:59 GMT"`). Returns ``None`` when the value is
    absent or unparseable.
    """
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None

    try:
        return max(0.0, float(value))
    except ValueError:
        pass

    try:
        target = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None

    now = dt.datetime.now(tz=target.tzinfo) if target.tzinfo else dt.datetime.now()
    delta = (target - now).total_seconds()
    return max(0.0, delta)


def _backoff_delay(attempt: int, base_delay: float, max_delay: float) -> float:
    # Decorrelated jitter: pick uniformly in [base_delay, capped]; the upper
    # bound is the exponential schedule, clamped to max_delay so the result is
    # guaranteed <= max_delay.
    exp = base_delay * (2 ** (attempt - 1))
    capped = min(exp, max_delay)
    upper = max(base_delay, capped)
    return random.uniform(base_delay, upper)


async def with_retry[T](
    func: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> T:
    """Invoke ``func`` with retry on :class:`RateLimitError`.

    Behaviour:
      - On a 429 with ``Retry-After``, sleep at least that long.
      - On a 429 without ``Retry-After``, exponential backoff with jitter.
      - All other exceptions bubble up immediately — the caller decides
        whether they are retryable.

    The ``sleep`` parameter is injectable so tests can verify timing without
    actually waiting.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    log = get_logger(component="retry")
    last_exc: RateLimitError | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            return await func()
        except RateLimitError as exc:
            last_exc = exc
            if attempt == max_attempts:
                log.warning("retry_giving_up", attempts=attempt)
                raise

            if exc.retry_after is not None:
                delay = min(max(exc.retry_after, 0.0), max_delay)
            else:
                delay = _backoff_delay(attempt, base_delay, max_delay)

            log.info(
                "retry_scheduled",
                attempt=attempt,
                next_attempt=attempt + 1,
                delay_seconds=round(delay, 3),
                retry_after=exc.retry_after,
            )
            await sleep(delay)

    assert last_exc is not None
    raise last_exc
