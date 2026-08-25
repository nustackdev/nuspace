"""Snippet load path: source string -> Nu term via parse_snippet."""

from __future__ import annotations

import pytest

import nu
from nuspace.snippets import parse_snippet


def test_parses_minimal_snippet():
    term = parse_snippet("nu.Str('hi')", path="test")
    assert isinstance(term, nu.Nu)


def test_scope_exposes_nu_and_space():
    term = parse_snippet("nu.Str(str(type(Space).__name__))", path="test")
    assert isinstance(term, nu.Nu)


def test_non_nu_return_raises():
    with pytest.raises(TypeError):
        parse_snippet("42", path="test")
