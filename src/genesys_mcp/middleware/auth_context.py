"""Per-request auth context — replaces the incumbent's module-global flag."""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from contextvars import ContextVar
from dataclasses import dataclass

from pydantic import SecretStr


@dataclass(frozen=True)
class AuthContext:
    """Authentication state for a single in-flight request.

    Holding this in a :class:`contextvars.ContextVar` means each MCP request
    (and each concurrent asyncio task) sees its own copy. There is deliberately
    no module-global ``isAuthenticated`` flag — that pattern is what breaks
    the incumbent's wrapper for long-running sessions and multi-tenant callers.

    The ``access_token`` is wrapped in :class:`pydantic.SecretStr` and the
    ``__repr__`` / ``__str__`` mask its presence so structured logs cannot
    accidentally leak it.
    """

    client_id: str | None = None
    access_token: SecretStr | None = None
    region: str | None = None
    tenant: str | None = None

    @property
    def is_authenticated(self) -> bool:
        return self.access_token is not None

    def __repr__(self) -> str:
        token_repr = "<set>" if self.access_token is not None else "None"
        return (
            "AuthContext("
            f"client_id={self.client_id!r}, "
            f"access_token={token_repr}, "
            f"region={self.region!r}, "
            f"tenant={self.tenant!r})"
        )

    def __str__(self) -> str:
        return self.__repr__()


_EMPTY_AUTH_CONTEXT = AuthContext()
_auth_context_var: ContextVar[AuthContext | None] = ContextVar(
    "genesys_mcp_auth_context",
    default=None,
)


def current_auth_context() -> AuthContext:
    """Return the auth context bound to the current task, or an empty default."""
    return _auth_context_var.get() or _EMPTY_AUTH_CONTEXT


@contextlib.contextmanager
def bind_auth_context(ctx: AuthContext) -> Iterator[AuthContext]:
    """Bind ``ctx`` for the duration of the ``with`` block.

    Restoration happens via the contextvar token even if the body raises, so
    no auth state ever leaks across requests or concurrent tasks.
    """
    token = _auth_context_var.set(ctx)
    try:
        yield ctx
    finally:
        _auth_context_var.reset(token)
