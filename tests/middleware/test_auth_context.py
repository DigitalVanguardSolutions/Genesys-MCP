"""Auth context isolation across concurrent asyncio tasks."""

from __future__ import annotations

import asyncio

from pydantic import SecretStr

from genesys_mcp.middleware.auth_context import (
    AuthContext,
    bind_auth_context,
    current_auth_context,
)


def test_default_context_is_empty() -> None:
    ctx = current_auth_context()
    assert ctx.is_authenticated is False
    assert ctx.access_token is None


def test_bind_and_restore() -> None:
    ctx = AuthContext(access_token=SecretStr("tok"), region="mypurecloud.com")
    with bind_auth_context(ctx):
        bound = current_auth_context()
        assert bound is ctx
        assert bound.is_authenticated is True
    assert current_auth_context().access_token is None


def test_bind_restores_on_exception() -> None:
    ctx = AuthContext(access_token=SecretStr("tok"))
    try:
        with bind_auth_context(ctx):
            raise RuntimeError("kaboom")
    except RuntimeError:
        pass
    assert current_auth_context().access_token is None


async def test_concurrent_tasks_have_isolated_contexts() -> None:
    """Two tasks bind different contexts and must not see each other's state."""

    barrier = asyncio.Event()
    seen: dict[str, str | None] = {}

    async def task(label: str, token: str) -> None:
        with bind_auth_context(
            AuthContext(access_token=SecretStr(token), tenant=label)
        ):
            await barrier.wait()
            await asyncio.sleep(0)
            ctx = current_auth_context()
            assert ctx.access_token is not None
            seen[label] = ctx.access_token.get_secret_value()
            assert ctx.tenant == label

    t1 = asyncio.create_task(task("a", "token-a"))
    t2 = asyncio.create_task(task("b", "token-b"))

    await asyncio.sleep(0)
    barrier.set()
    await asyncio.gather(t1, t2)

    assert seen == {"a": "token-a", "b": "token-b"}
    assert current_auth_context().access_token is None


async def test_no_module_global_state_leaks_across_runs() -> None:
    """Sanity check: a context bound in one task is invisible in another."""

    captured: list[AuthContext] = []

    async def reader() -> None:
        captured.append(current_auth_context())

    with bind_auth_context(AuthContext(access_token=SecretStr("parent-token"))):
        await asyncio.gather(reader())

    await asyncio.gather(reader())

    assert captured[0].access_token is not None
    assert captured[0].access_token.get_secret_value() == "parent-token"
    assert captured[1].access_token is None


def test_repr_does_not_leak_token() -> None:
    ctx = AuthContext(access_token=SecretStr("super-secret"))
    rendered_repr = repr(ctx)
    rendered_str = str(ctx)
    rendered_format = f"event={ctx}"
    assert "super-secret" not in rendered_repr
    assert "super-secret" not in rendered_str
    assert "super-secret" not in rendered_format
    assert "<set>" in rendered_repr


def test_repr_marks_unset_token_as_none() -> None:
    ctx = AuthContext()
    rendered = repr(ctx)
    assert "access_token=None" in rendered
    assert "<set>" not in rendered
