"""Content: a kind's schema and form, its typed accessors, where items land, their lifecycle, registry and space info."""

from __future__ import annotations

import warnings

import pytest
from _support.contents import Note, NoteContent, PlainContent, write
from _support.made import MADE
from _support.specs import CONTENTS

import nu
import nuspace
import nustd.kv
from nuspace import content, ops
from nuspace.content import CELL, PLANE, SPACE, SearchField, kind_name
from nuspace.ext import (
    ContentSpec,
    Extension,
    Registry,
    RegistryWarning,
    content_spec,
    space_registry,
)
from nuspace.shapes import Reroot, Space, States


#: Run on both backends: in memory, and the space's sqlite files.
STORES = ("memory", "sqlite")

NOTE = "testing.Note"
PLAIN = "testing.Plain"
NOTE_SPEC, PLAIN_SPEC = CONTENTS


def in_run(plane_id: str, cell_id: str, term: nu.Nu) -> nu.Nu:
    """``term`` as a program in a run: rerooted as the kernel does at load, one commit to States."""
    return ops.atomic_state(Reroot(plane_id, cell_id)(term))


# --- A kind --------------------------------------------------------------------------------


def test_a_kind_is_its_declared_name_and_its_schema_comes_off_the_generic():
    assert (NoteContent.name, kind_name(NoteContent)) == ("Note", NOTE)
    assert content_spec(NOTE) is NOTE_SPEC
    assert content_spec(NOTE).kind is NoteContent
    assert NoteContent.schema() is Note
    assert PlainContent.schema() is Note

    class Deeper(NoteContent, name="Deeper"):
        pass

    assert Deeper.schema() is Note


def test_a_spec_names_its_kind_and_labels_it():
    assert (NOTE_SPEC.name, NOTE_SPEC.label) == ("Note", "Note")
    assert (PLAIN_SPEC.name, PLAIN_SPEC.label) == ("Plain", "Plain note")
    assert NOTE_SPEC.description.startswith("A note")
    assert ContentSpec(nuspace.Content).label == "Content"
    with pytest.raises(TypeError, match="no Content subclass"):
        ContentSpec(Note)


def test_a_kind_with_no_schema_or_no_name_and_a_name_of_no_kind_are_refused():
    with pytest.raises(TypeError, match="names no schema"):
        nuspace.Content.schema()
    with pytest.raises(TypeError, match="declares no name"):

        class Nameless(nuspace.Content[Note]):
            pass

    with pytest.raises(ValueError, match="no dots"):

        class Dotted(nuspace.Content[Note], name="a.b"):
            pass

    with pytest.raises(LookupError):
        content_spec("nowhere.at_all")


def test_the_form_is_generated_from_match_keywords():
    assert NoteContent.form() == (
        SearchField("text", "text", "Text"),
        SearchField("min_stars", "number", "Min stars"),
        SearchField("done", "switch", "Done"),
    )
    assert PlainContent.form() == ()


def test_a_kind_can_write_its_own_form():
    class Asked(nuspace.Content[Note], name="Asked"):
        @classmethod
        def form(cls):
            return (SearchField("text", "text", "Words"),)

    assert Asked.form() == (SearchField("text", "text", "Words"),)


def test_defaults_match_everything_and_draw_nothing():
    item = PlainContent.space("x")
    assert nu.run(PlainContent.match(item))[0] is True
    assert isinstance(PlainContent.render(item), nu.Noop)
    assert isinstance(PlainContent.render_hit(item), nu.Noop)


def test_match_branches_on_what_was_asked_at_construction():
    item = NoteContent.space("x")
    assert isinstance(NoteContent.match(item), nu.Bool)
    asked = NoteContent.match(item, text="a")
    both = NoteContent.match(item, text="a", done=True)
    assert nu.tree.size(asked) < nu.tree.size(both)


def test_accessors_return_the_kinds_shape_typed():
    for ref in (
        NoteContent.cell("x"),
        NoteContent.plane("x"),
        NoteContent.space("x"),
        NoteContent.at((CELL, "c"), "x"),
        NoteContent.at((PLANE, "p"), "x"),
        NoteContent.at((SPACE, ""), "x"),
    ):
        assert isinstance(ref, nustd.kv.ShapeRef)
        assert isinstance(ref.body, nustd.kv.StrRef)
        assert isinstance(ref.stars, nustd.kv.FloatRef)
        assert isinstance(ref.done, nustd.kv.BoolRef)
    assert nu.shape.root_shape(NoteContent.space("x").body) is States
    with pytest.raises(ValueError, match="scope level"):
        NoteContent.at(("shelf", "s"), "x")


# --- Where items live -------------------------------------------------------------------------


async def test_items_land_by_kind_then_scope_then_id(store):
    await store.run(
        write(NoteContent, (CELL, "c1"), "a", body="in a cell", stars=2.0)
        >> write(NoteContent, (PLANE, "p1"), "b", body="on a plane")
        >> write(NoteContent, (SPACE, ""), "c", done=True)
        >> write(PlainContent, (CELL, "c1"), "a", body="plain")
    )
    assert await store.read(States.contents.extract()) == {
        NOTE: {
            "cells": {"c1": {"a": {"body": "in a cell", "stars": 2.0}}},
            "planes": {"p1": {"b": {"body": "on a plane"}}},
            "space": {"c": {"done": True}},
        },
        PLAIN: {"cells": {"c1": {"a": {"body": "plain"}}}},
    }
    assert await store.read(NoteContent.at((CELL, "c1"), "a").body) == "in a cell"


async def test_cell_and_plane_items_land_under_the_running_cell_and_plane(store):
    term = (
        NoteContent.cell("summary").body.set("mine")
        >> NoteContent.plane("title").body.set("ours")
        >> PlainContent.cell("summary").body.set("plain")
        >> NoteContent.space("readme").body.set("everyone's")
    )
    await store.run(in_run("p", "c", term))
    await store.run(in_run("p", "d", NoteContent.cell("summary").body.set("theirs")))
    held = await store.read(States.contents.extract())
    assert held[NOTE]["cells"] == {
        "c": {"summary": {"body": "mine"}},
        "d": {"summary": {"body": "theirs"}},
    }
    assert held[NOTE]["planes"] == {"p": {"title": {"body": "ours"}}}
    assert held[NOTE]["space"] == {"readme": {"body": "everyone's"}}
    assert held[PLAIN]["cells"] == {"c": {"summary": {"body": "plain"}}}
    # Read back the same way, and from outside by address.
    assert await store.read(Reroot("p", "c")(NoteContent.cell("summary").body)) == "mine"
    assert await store.read(ops.cell_state("d", NoteContent.cell("summary").body)) == "theirs"
    assert await store.read(ops.plane_state("p", NoteContent.plane("title").body)) == "ours"


def test_a_term_with_no_items_comes_back_as_it_was():
    term = nu.Str("x") + "y"
    assert Reroot("p", "c")(term) is term


async def test_a_loaded_program_keeps_items_through_the_kernel_rewrite(store):
    prog = """\
import nuspace
from _support.contents import NoteContent


def out():
    return nuspace.ops.atomic_state(NoteContent.cell("summary").body.set("loaded"))
"""
    await store.run(ops.add_plane("p", backend="async") >> ops.add_cell("p", prog, cell_id="c"))
    load = Space.cells["c"].prog.load(scope={"plane": "p", "cell": "c"}, rewrite=Reroot("p", "c"))
    term = await store.run(nustd.kv.Snapshot(load, scope=Space))
    await store.run(term)
    assert await store.read(NoteContent.at((CELL, "c"), "summary").body) == "loaded"


# --- items, new, find --------------------------------------------------------------------------


async def test_items_is_one_scopes_items_by_id_typed_as_the_kinds_shape(store):
    await store.run(
        write(NoteContent, (CELL, "c1"), "a", body="one")
        >> write(NoteContent, (CELL, "c1"), "b", body="two")
        >> write(NoteContent, (CELL, "c2"), "a", body="elsewhere")
        >> write(NoteContent, (SPACE, ""), "s", body="space")
    )
    held = NoteContent.items((CELL, "c1"))
    assert isinstance(held, nustd.kv.DictRef)
    assert isinstance(held["a"].body, nustd.kv.StrRef)
    assert sorted(await store.read(nu.list(held.keys()))) == ["a", "b"]
    assert await store.read(held["b"].body) == "two"
    assert await store.read(nu.list(NoteContent.items((SPACE, "")).keys())) == ["s"]
    assert await store.read(NoteContent.items((PLANE, "p")).len()) == 0
    # An item removed through the mapping is gone from it.
    await store.run(ops.atomic_state(held["a"].erase()))
    assert await store.read(nu.list(held.keys())) == ["b"]
    with pytest.raises(ValueError, match="scope level"):
        NoteContent.items(("shelf", "s"))


async def test_new_makes_an_empty_item_under_a_fresh_ordered_id(store):
    scope = (PLANE, "p")
    first = await store.made(ops.atomic_state(NoteContent.new(scope, into=MADE)))
    second = await store.made(ops.atomic_state(NoteContent.new(scope, into=MADE)))
    assert first != second
    assert first.startswith(content.ITEM_PREFIX + "_")
    # Listed at once, in the order made, before a field is set.
    assert await store.read(nu.list(NoteContent.items(scope).keys())) == [first, second]
    assert await store.read(NoteContent.at(scope, first).extract()) == {}
    # Without into, it only makes one.
    await store.run(ops.atomic_state(NoteContent.new(scope)))
    assert await store.read(NoteContent.items(scope).len()) == 3


async def test_find_walks_every_scope_cells_then_planes_then_space(store):
    await store.run(
        write(NoteContent, (SPACE, ""), "s", body="basil in the space")
        >> write(NoteContent, (PLANE, "p"), "t", body="basil on a plane", stars=4.0)
        >> write(NoteContent, (CELL, "c"), "a", body="basil in a cell", stars=1.0)
        >> write(NoteContent, (CELL, "c"), "b", body="mint")
        >> write(PlainContent, (CELL, "c"), "a", body="basil, another kind")
    )
    found = await store.read(NoteContent.find(text="basil"))
    assert [(a["kind"], list(a["scope"]), a["id"]) for a, _ in found] == [
        (NOTE, [CELL, "c"], "a"),
        (NOTE, [PLANE, "p"], "t"),
        (NOTE, [SPACE, ""], "s"),
    ]
    assert found[0][1] == {"body": "basil in a cell", "stars": 1.0}
    both = await store.read(NoteContent.find(text="basil", min_stars=2))
    assert [a["id"] for a, _ in both] == ["t"]
    # Asked nothing, everything match lets through: every item of the kind.
    assert len(await store.read(NoteContent.find())) == 4
    # A keyword match does not take is refused when the term is built.
    with pytest.raises(TypeError):
        PlainContent.find(text="basil")


async def test_find_runs_from_a_loaded_program(store):
    prog = """\
import nu
import nuspace
from _support.contents import NoteContent


def first(found):
    address = nu.Dict(nu.List(nu.List(found)[0])[0])
    return NoteContent.cell("found").body.set(nu.str(address["id"]))


def out():
    found = nuspace.ops.snapshot(NoteContent.find(text="basil"))
    return nuspace.ops.atomic_state(nu.let(found, first))
"""
    await store.run(
        write(NoteContent, (PLANE, "p"), "t", body="basil")
        >> ops.add_plane("p", backend="async")
        >> ops.add_cell("p", prog, cell_id="c")
    )
    load = Space.cells["c"].prog.load(scope={"plane": "p", "cell": "c"}, rewrite=Reroot("p", "c"))
    await store.run(await store.run(nustd.kv.Snapshot(load, scope=Space)))
    assert await store.read(NoteContent.at((CELL, "c"), "found").body) == "t"


# --- Lifecycle --------------------------------------------------------------------------------


async def _tree(store) -> tuple[str, str, str]:
    """A plane ``p`` with cells ``c1``, ``c2``, items of both kinds on each, the plane and the space."""
    p = await store.made(ops.add_plane("p", backend="async", into=MADE))
    c1 = await store.made(ops.add_cell(p, "", cell_id="c1", into=MADE))
    c2 = await store.made(ops.add_cell(p, "", cell_id="c2", into=MADE))
    for kind in (NoteContent, PlainContent):
        await store.run(
            write(kind, (CELL, c1), "x", body="1")
            >> write(kind, (CELL, c2), "x", body="2")
            >> write(kind, (PLANE, p), "x", body="p")
            >> write(kind, (SPACE, ""), "x", body="s")
        )
    return p, c1, c2


async def test_removing_a_cell_drops_its_items_of_every_kind(store):
    p, c1, c2 = await _tree(store)
    await store.run(ops.remove_cell(c1))
    for name in (NOTE, PLAIN):
        assert await store.read(nu.list(States.contents[name].cells.keys())) == [c2]
        assert await store.read(nu.list(States.contents[name].planes.keys())) == [p]


async def test_removing_a_plane_drops_its_items_and_its_cells(store):
    p, _, _ = await _tree(store)
    await store.run(
        ops.add_plane("q", backend="async", parent=p)
        >> write(NoteContent, (PLANE, "q"), "x", body="q")
    )
    await store.run(ops.remove_plane(p))
    for name in (NOTE, PLAIN):
        held = await store.read(States.contents[name].extract())
        assert held.get("cells", {}) == {} and held.get("planes", {}) == {}
        assert held["space"] == {"x": {"body": "s"}}


async def test_items_of_a_cell_that_is_there_are_kept(store):
    _, c1, _ = await _tree(store)
    await store.run(ops.atomic_state(ops.state.drop_cell_state(c1)))
    assert await store.read(NoteContent.at((CELL, c1), "x").body) == "1"


# --- Registry and space info ---------------------------------------------------------------


def test_kinds_register_by_package_and_name_one_name_per_kind():
    first = Extension(contents=(NOTE_SPEC, PLAIN_SPEC))
    second = Extension(contents=(ContentSpec(NoteContent, label="Again"),))
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        reg = Registry.merge({"first": first, "second": second})
    assert dict(reg.contents) == {"first.Note": NOTE_SPEC, "first.Plain": PLAIN_SPEC}
    said = [str(w.message) for w in caught if issubclass(w.category, RegistryWarning)]
    assert said == ["Content 'second.Note' ignored: its kind is registered as 'first.Note'"]


def test_a_kind_no_installed_package_adds_has_no_name():
    class Loose(nuspace.Content[Note], name="Loose"):
        pass

    with pytest.raises(LookupError, match="not installed"):
        kind_name(Loose)
    with pytest.raises(LookupError):
        Loose.cell("x")


def test_the_installed_kinds_register_with_the_space():
    assert list(space_registry(extensions=["testing"]).contents) == [NOTE, PLAIN]
    assert {NOTE, PLAIN} <= set(space_registry().contents)
