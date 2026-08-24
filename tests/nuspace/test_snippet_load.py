"""Snippet load path: text_snippet -> parse_snippet -> Nu term."""

from __future__ import annotations

import nu
from nuspace.snippets import parse_snippet, text_snippet


def test_text_snippet_bakes_app_id():
    src = text_snippet("b_abc")
    assert "b_abc" in src
    assert "nu.ReactForever" in src


def test_parse_snippet_returns_sequential():
    src = text_snippet("b_xyz")
    term = parse_snippet(src, "apps/b_xyz")
    assert isinstance(term, nu.Nu)
    # Sequential(InputRef.set(seed), ReactForever(changed, StrRef.set(...)))
    assert type(term).__name__ == "Sequential"


def test_parse_snippet_type_error_on_non_nu():
    import pytest

    with pytest.raises(TypeError):
        parse_snippet("42", "irrelevant")
