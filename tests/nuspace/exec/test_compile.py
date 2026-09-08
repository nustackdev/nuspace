"""Compiling a section: source in, Nu tree plus mount fields out."""

from __future__ import annotations

import pytest

import nu
from nuspace.exec import SectionCompileError, compile_section


def test_expression_form():
    term, fields = compile_section("nu.ui.TextRef(path + '.out').set(nu.Str('hi'))", "sections.s1")
    assert isinstance(term, nu.Nu)
    assert fields == [{"path": "sections.s1.out", "type": "TextRef"}]


def test_script_form_with_trailing_expression():
    source = (
        "class Movie(nu.Shape):\n"
        "    title = nu.kv.StrRef.slot()\n"
        "\n"
        "nu.ui.TextRef(path + '.name').set(nu.Str(Movie.__name__))\n"
    )
    term, fields = compile_section(source, "sections.s1")
    assert isinstance(term, nu.Nu)
    assert fields[0]["path"] == "sections.s1.name"


def test_script_form_with_entry_point():
    source = "def section():\n    return nu.ui.TextRef(path + '.out').set(nu.Str('hi'))\n"
    term, _ = compile_section(source, "sections.s1")
    assert isinstance(term, nu.Nu)


def test_script_form_binding_tree():
    source = "tree = nu.ui.TextRef(path + '.out').set(nu.Str('hi'))\nx = 1\n"
    term, _ = compile_section(source, "sections.s1")
    assert isinstance(term, nu.Nu)


def test_syntax_error_is_a_diagnostic_with_a_line():
    with pytest.raises(SectionCompileError) as excinfo:
        compile_section("x = (\n", "sections.s1")
    assert excinfo.value.line == 1
    assert "SyntaxError" in excinfo.value.diagnostic()


def test_build_error_carries_the_section_line():
    with pytest.raises(SectionCompileError) as excinfo:
        compile_section("x = 1\ny = 1 / 0\n", "sections.s1")
    assert excinfo.value.line == 2
    assert "ZeroDivisionError" in excinfo.value.diagnostic()


def test_non_nu_result_is_rejected():
    with pytest.raises(SectionCompileError, match="expected a Nu term"):
        compile_section("42", "sections.s1")


def test_empty_source_is_rejected():
    with pytest.raises(SectionCompileError, match="no tree"):
        compile_section("x = 1\n", "sections.s1")


def test_only_own_prefix_mounts():
    """A borrowed ref is a live wire, not a second mount."""
    source = "nu.ui.TextRef(path + '.out').set(nu.ui.InputRef('sections.other.text'))"
    _, fields = compile_section(source, "sections.s1")
    assert [f["path"] for f in fields] == ["sections.s1.out"]


def test_fields_are_deduplicated():
    source = (
        "nu.ui.TextRef(path + '.out').set(nu.Str('a')) | "
        "nu.ui.TextRef(path + '.out').set(nu.Str('b'))"
    )
    _, fields = compile_section(source, "sections.s1")
    assert len(fields) == 1
