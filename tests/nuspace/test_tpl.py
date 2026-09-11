"""tpl: provenance, not type.

The claims worth pinning, because they are the ones the rest of the surface
leans on:

- a text block is a **real Nu program**. It constructs, and it mounts exactly
  one ui ref, at the one path the browser and kv both address it by.
- ``tpl`` never gates anything. An unknown value is a program, because every
  block is a program.
- the tier reaches the supervisor's spec without anyone re-reading kv.
"""

from __future__ import annotations

from nu.prog import Diagnostic
from nuspace.core.shapes import Space
from nuspace.core.tpl import PROGRAM, TEXT, TPL_PROGRAM, TPL_TEXT, resolve
from nuspace.exec.compile import construct_section, enumerate_ui_refs
from nuspace.exec.status import SectionSpec
from nuspace.web.refs.pages.store import tpl_of


# -- the registry ------------------------------------------------------------


def test_unknown_tpl_is_a_program():
    """No invalid value to reject: a block with no tpl is still a program."""
    assert resolve(None) is PROGRAM
    assert resolve("") is PROGRAM
    assert resolve("wysiwyg-2000") is PROGRAM
    assert tpl_of({}) is PROGRAM
    assert tpl_of({"tpl": TPL_TEXT}) is TEXT


def test_program_content_is_its_own_snippet():
    """Arbitrary tpl: what you typed IS the program, so there is no content key."""
    assert PROGRAM.content_key("s1") is None
    assert PROGRAM.source(Space, "nu.Str('x')") == "nu.Str('x')"


def test_program_with_no_content_gets_the_starter():
    src = PROGRAM.source(Space, "")
    assert "def out(path):" in src


def test_text_content_key_is_also_its_mount_path():
    """One address, both directions: kv key == browser ref path."""
    assert TEXT.content_key("s1") == "sections.s1.text"


def test_text_source_names_the_spaces_own_root_class():
    """ShapeMeta rebinds `_root_shape`, so a subclass is a different address."""

    class Sub(Space):
        pass

    src = TEXT.source(Sub)
    assert "import Sub" in src
    assert "Sub.state" in src


# -- the text block is a program ---------------------------------------------


def test_text_template_constructs():
    term = construct_section(TEXT.source(Space), "sections.s1")
    assert not isinstance(term, Diagnostic), term


def test_text_template_mounts_exactly_one_prose_ref():
    term = construct_section(TEXT.source(Space), "sections.s1")
    assert enumerate_ui_refs(term, "sections.s1") == [
        {"path": "sections.s1.text", "type": "ProseRef"},
    ]


def test_every_text_block_holds_the_same_program():
    """The batching claim. Two text blocks differ only by `path`, which is scope."""
    assert TEXT.source(Space) == TEXT.source(Space)


# -- the tier reaches the spec -----------------------------------------------


def test_spec_carries_the_tier():
    assert SectionSpec("s1", "x", tpl=TPL_TEXT).tier == "batch"
    assert SectionSpec("s1", "x", tpl=TPL_PROGRAM).tier == "standing"


def test_spec_defaults_to_a_standing_program():
    """A spec built without a tpl is arbitrary code until told otherwise."""
    assert SectionSpec("s1", "x").tier == "standing"
