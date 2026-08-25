"""Shape + ref wiring tests. End-to-end persistence lives in examples/."""

from __future__ import annotations

import nu
from nuspace import Space
from nuspace.core.refs import AppRef, AppsRef, SectionRef, SectionsRef


def test_ref_types_are_nuspace_subclasses():
    assert issubclass(AppsRef, nu.kv.ShapesDictRef)
    assert issubclass(SectionsRef, nu.kv.ShapesDictRef)


def test_descent_returns_nuspace_typed_item_refs():
    assert isinstance(Space.apps["x"], AppRef)
    assert isinstance(Space.pages["home"].sections["s"], SectionRef)


def test_add_returns_a_nu_term():
    t1 = Space.apps.add("nu.Str('hi')", policy="always", app_id="a_test")
    t2 = Space.pages["home"].sections.add("nu.Str('body')", policy="on_navigate", section_id="s1")
    assert isinstance(t1, nu.Nu)
    assert isinstance(t2, nu.Nu)


def test_slot_descent_yields_nu_terms():
    assert isinstance(Space.apps["a_test"].snippet, nu.Nu)
    assert isinstance(Space.pages["home"].sections["s1"].policy, nu.Nu)


def test_run_returns_eval_term():
    run_term = Space.apps["a_test"].run()
    assert isinstance(run_term, nu.Nu)
    # PyCall+Eval structure
    assert type(run_term).__name__ == "Eval"
