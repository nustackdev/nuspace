"""PagesRef wire-shape unit tests: tree folding, section mounting, walking."""

from __future__ import annotations

import pytest

import nu
import nu.ui
from nuspace import Space
from nuspace.snippets import parse_snippet
from nuspace.web.nuspace_ui import PagesPage
from nuspace.web.refs.pages.pages import (
    MAX_CHILD_PAGES,
    MAX_PAGE_DEPTH,
    PagesDriver,
    PagesRef,
    _enumerate_ui_refs,
    _fold,
    _page_node,
    _page_ref,
    _parent_pages,
)


# -- Ref wiring --------------------------------------------------------------


def test_ref_is_registered_under_its_wire_type():
    assert PagesRef._wire_type_override == "PagesRef"


def test_page_slot_mounts_one_field():
    fields = PagesPage._mount_fields()
    assert fields == [{"path": "PagesPage.pages", "type": "PagesRef"}]


def test_payload_is_frozen_at_construction():
    ref = PagesRef("pages", space_root=Space)
    assert ref._payload["pages_space_root"] is Space
    # Nothing runtime-ish sneaks onto the payload.
    assert "path" not in ref._payload
    assert "mode" not in ref._payload


def test_verbs_return_nu_terms():
    ref = PagesPage.pages
    assert isinstance(ref.set_tree({"id": None, "title": "", "pages": []}), nu.Nu)
    assert isinstance(ref.set_page({"page_id": None, "sections": []}), nu.Nu)
    assert isinstance(ref.feedback(), nu.Nu)
    assert isinstance(PagesDriver(ref), nu.Nu)


# -- Substrate walking -------------------------------------------------------


def test_page_ref_walk_is_recursive():
    assert _page_ref(Space, []) is not None
    deep = _page_ref(Space, ["a", "b", "c"])
    assert isinstance(deep.title, nu.Nu)


def test_parent_pages_splits_the_path():
    container, pid = _parent_pages(Space, ["a", "b"])
    assert pid == "b"
    assert isinstance(container["b"], nu.Nu)


def test_root_page_has_no_parent():
    with pytest.raises(ValueError, match="root page"):
        _parent_pages(Space, [])


# -- Tree payload ------------------------------------------------------------


def test_page_node_folds_nested_extract():
    data = {
        "title": "Space",
        "sections": {"s_x": {"name": "n"}},
        "pages": {
            "p_a": {"title": "A", "pages": {"p_b": {"title": "B", "pages": {}}}},
        },
    }
    node = _page_node(data, None, 0)
    assert node["id"] is None
    assert node["title"] == "Space"
    assert node["pages"][0]["id"] == "p_a"
    assert node["pages"][0]["pages"][0]["title"] == "B"
    # Sections are parts of a page, never sidebar entries.
    assert "sections" not in node


def test_page_node_survives_garbage():
    assert _page_node(None, "p", 0) == {"id": "p", "title": "p", "pages": []}


def test_page_node_caps_breadth_and_depth():
    wide = {"title": "w", "pages": {f"p{i:04d}": {"title": "x"} for i in range(300)}}
    assert len(_page_node(wide, None, 0)["pages"]) == MAX_CHILD_PAGES

    deep: dict = {"title": "leaf", "pages": {}}
    for _ in range(MAX_PAGE_DEPTH + 5):
        deep = {"title": "n", "pages": {"p": deep}}
    node = _page_node(deep, None, 0)
    depth = 0
    while node["pages"]:
        node = node["pages"][0]
        depth += 1
    assert depth == MAX_PAGE_DEPTH


# -- Section mounting --------------------------------------------------------


def test_enumerate_ui_refs_namespaces_by_section_id():
    src = (
        "nu.ui.InputRef(path + '.text').set(nu.Str('x'))"
        " >> nu.ui.StatRef(path + '.echo').set_value(nu.Str('y'))"
    )
    fields = _enumerate_ui_refs(parse_snippet(src, "sections.s_abc"))
    assert fields == [
        {"path": "sections.s_abc.text", "type": "InputRef"},
        {"path": "sections.s_abc.echo", "type": "StatRef"},
    ]


def test_enumerate_ui_refs_dedupes_by_type_and_path():
    src = (
        "nu.ReactForever(nu.ui.InputRef(path + '.t').changed(),"
        " nu.ui.InputRef(path + '.t').set(nu.Str(nu.ui.InputRef(path + '.t'))))"
    )
    fields = _enumerate_ui_refs(parse_snippet(src, "sections.s1"))
    assert fields == [{"path": "sections.s1.t", "type": "InputRef"}]


def test_enumerate_ui_refs_ignores_pure_kv_snippets():
    assert _enumerate_ui_refs(parse_snippet("nu.Str('no ui here')", "sections.s1")) == []


def test_fold_joins_sections_in_parallel():
    terms = [parse_snippet(f"nu.Str({i!r})", f"sections.s{i}") for i in range(3)]
    folded = _fold(terms)
    assert isinstance(folded, nu.Nu)
    assert len(_fold(terms[:1])._children) == len(terms[0]._children)


def test_bad_snippet_raises_so_the_driver_can_degrade_one_section():
    with pytest.raises(Exception):  # noqa: B017 -- any parse failure is caught upstream
        parse_snippet("this is not python(((", "sections.s1")
