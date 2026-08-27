"""Shape + ref wiring tests. End-to-end persistence lives in examples/."""

from __future__ import annotations

import nu
from nuspace import Space
from nuspace.core.refs import (
    AppRef,
    AppsRef,
    GroupRef,
    PageRef,
    PagesRef,
    SectionRef,
    SectionsRef,
    mint_ordered_id,
)


def test_ref_types_are_nuspace_subclasses():
    assert issubclass(AppsRef, nu.kv.ShapesDictRef)
    assert issubclass(SectionsRef, nu.kv.ShapesDictRef)
    assert issubclass(PagesRef, nu.kv.ShapesDictRef)


def test_apps_root_is_a_group():
    assert isinstance(Space.apps, nu.kv.ShapeRef)
    assert isinstance(Space.apps.groups["g"], GroupRef)
    assert isinstance(Space.apps.apps["a"], AppRef)


def test_pages_root_is_a_page():
    """Space.pages is the root Page; its children are the top-level pages."""
    assert isinstance(Space.pages, nu.kv.ShapeRef)
    assert isinstance(Space.pages.pages["p"], PageRef)


def test_pages_nest_recursively():
    deep = Space.pages.pages["p_a"].pages["p_b"].pages["p_c"]
    assert isinstance(deep, PageRef)
    assert isinstance(deep.sections["s"], SectionRef)


def test_root_page_carries_sections():
    assert isinstance(Space.pages.sections["s"], SectionRef)


def test_add_returns_a_nu_term():
    t1 = Space.apps.apps.add(snippet="nu.Str('hi')", policy="always", app_id="a_test")
    t2 = Space.pages.pages.add(title="Home", page_id="p_home")
    t3 = Space.pages.pages["p_home"].sections.add(
        snippet="nu.Str('body')",
        policy="on_navigate",
        section_id="s1",
    )
    assert all(isinstance(t, nu.Nu) for t in (t1, t2, t3))


def test_slot_descent_yields_nu_terms():
    assert isinstance(Space.apps.apps["a_test"].snippet, nu.Nu)
    assert isinstance(Space.pages.pages["p_home"].sections["s1"].policy, nu.Nu)
    assert isinstance(Space.pages.pages["p_home"].title, nu.Nu)


def test_state_slot_is_addressable():
    assert isinstance(Space.state["anything"], nu.Nu)


def test_run_returns_eval_term():
    run_term = Space.apps.apps["a_test"].run()
    assert isinstance(run_term, nu.Nu)
    # PyCall+Eval structure
    assert type(run_term).__name__ == "Eval"


def test_ordered_ids_sort_by_creation():
    ids = [mint_ordered_id("s") for _ in range(5)]
    assert ids == sorted(ids)
    assert len(set(ids)) == 5
