"""Logging setup: request id contextvar discipline and input validation."""

from __future__ import annotations

import re

import pytest

from genesys_mcp.logging_setup import (
    clear_request_id,
    get_request_id,
    new_request_id,
    set_request_id,
)


def test_new_request_id_matches_validation_pattern() -> None:
    rid = new_request_id()
    assert re.fullmatch(r"[A-Za-z0-9_-]{1,64}", rid)
    assert get_request_id() == rid


def test_set_request_id_accepts_valid_ids() -> None:
    set_request_id("abc-123_DEF")
    assert get_request_id() == "abc-123_DEF"
    set_request_id("a")
    assert get_request_id() == "a"
    set_request_id("x" * 64)
    assert get_request_id() == "x" * 64


def test_set_request_id_none_clears() -> None:
    set_request_id("abc")
    set_request_id(None)
    assert get_request_id() is None


@pytest.mark.parametrize(
    "bad",
    [
        "",  # empty
        "x" * 65,  # too long
        "has space",  # whitespace
        "with\nnewline",  # control char
        "with\x00null",  # control char
        "tab\there",  # tab
        "punct!",  # disallowed punctuation
        "slash/in/it",  # slash
    ],
)
def test_set_request_id_rejects_invalid_inputs(bad: str) -> None:
    with pytest.raises(ValueError, match="request_id"):
        set_request_id(bad)


def test_clear_request_id() -> None:
    set_request_id("abc")
    clear_request_id()
    assert get_request_id() is None
