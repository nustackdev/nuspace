"""Constructing a section: source in, Nu tree plus mount fields out.

Construction itself is ``nu.prog``'s and is tested there. What is pinned
here is nuspace's half of the contract: ``path`` is the one scope value
offered, a failure comes back as a ``Diagnostic`` rather than an
exception, and mount enumeration is by path prefix.
"""

from __future__ import annotations

import textwrap

import nu
from nu.prog import Diagnostic
from nuspace.exec import construct_section, enumerate_ui_refs


def src(text: str) -> str:
    return textwrap.dedent(text).lstrip()


SIMPLE = src("""
    import nu
    import nu.ui

    def out(path):
        return nu.ui.TextRef(path + '.out').set(nu.Str('hi'))
""")


def test_entry_point_form():
    term = construct_section(SIMPLE, "sections.s1")
    assert isinstance(term, nu.Nu)
    assert enumerate_ui_refs(term, "sections.s1") == [
        {"path": "sections.s1.out", "type": "TextRef"}
    ]


def test_a_module_can_mint_a_shape():
    """The reason source is a module and not an expression."""
    source = src("""
        import nu
        import nu.ui

        class Movie(nu.Shape):
            title = nu.kv.StrRef.slot()

        def out(path):
            return nu.ui.TextRef(path + '.name').set(nu.Str(Movie.__name__))
    """)
    term = construct_section(source, "sections.s1")
    assert isinstance(term, nu.Nu)
    assert enumerate_ui_refs(term, "sections.s1")[0]["path"] == "sections.s1.name"


def test_an_entry_point_that_wants_nothing_is_fine():
    source = src("""
        import nu
        import nu.ui

        def out():
            return nu.ui.TextRef('sections.s1.out').set(nu.Str('hi'))
    """)
    assert isinstance(construct_section(source, "sections.s1"), nu.Nu)


def test_the_space_shape_is_imported_not_injected():
    """Only plain data binds into an entry point; Space is a class."""
    source = src("""
        import nu
        import nu.ui
        from nuspace.core.shapes import Space

        def out(path):
            return nu.ui.TextRef(path + '.out').set(nu.Str(Space.state[path]))
    """)
    assert isinstance(construct_section(source, "sections.s1"), nu.Nu)


# -- diagnostics -------------------------------------------------------------


def test_syntax_error_is_a_diagnostic_with_a_line():
    diag = construct_section("def out(path:\n", "sections.s1")
    assert isinstance(diag, Diagnostic)
    assert diag.lineno == 1
    assert "does not parse" in str(diag)


def test_a_module_that_raises_carries_the_section_line():
    source = "x = 1\ny = 1 / 0\n"
    diag = construct_section(source, "sections.s1")
    assert isinstance(diag, Diagnostic)
    assert diag.lineno == 2
    assert "ZeroDivisionError" in diag.message


def test_a_missing_entry_point_is_a_diagnostic():
    diag = construct_section("x = 1\n", "sections.s1")
    assert isinstance(diag, Diagnostic)
    assert "entry point 'out'" in diag.message


def test_a_non_nu_return_is_a_diagnostic():
    diag = construct_section("def out(path):\n    return 42\n", "sections.s1")
    assert isinstance(diag, Diagnostic)
    assert "expected a Nu term" in diag.message


def test_a_scope_nuspace_does_not_offer_is_a_diagnostic():
    diag = construct_section("def out(session):\n    return session\n", "sections.s1")
    assert isinstance(diag, Diagnostic)
    assert "'session'" in diag.message
    assert "['path']" in diag.message


# -- mounting ----------------------------------------------------------------


def test_only_own_prefix_mounts():
    """A borrowed ref is a live wire, not a second mount."""
    source = src("""
        import nu
        import nu.ui

        def out(path):
            return nu.ui.TextRef(path + '.out').set(
                nu.ui.InputRef('sections.other.text'),
            )
    """)
    term = construct_section(source, "sections.s1")
    assert [f["path"] for f in enumerate_ui_refs(term, "sections.s1")] == ["sections.s1.out"]


def test_fields_are_deduplicated():
    source = src("""
        import nu
        import nu.ui

        def out(path):
            ref = nu.ui.TextRef(path + '.out')
            return ref.set(nu.Str('a')) | ref.set(nu.Str('b'))
    """)
    term = construct_section(source, "sections.s1")
    assert len(enumerate_ui_refs(term, "sections.s1")) == 1
