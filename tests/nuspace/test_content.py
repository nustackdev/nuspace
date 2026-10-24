"""Content: a kind's schema and form, its typed accessors, where items land, their lifecycle, registry and space info."""

from __future__ import annotations

import warnings

import pytest
from _support.contents import Note, NoteContent, PlainContent, write
from _support.made import MADE

import nu
import nuspace
import nustd.kv
from nuspace import content, ops
from nuspace.content import CELL, PLANE, SPACE, SearchField, kind_name, load_kind
from nuspace.ext import Extension, Registry, RegistryWarning, space_registry
from nuspace.shapes import Reroot, Space, States
from nuspace.system import home


#: Run on both backends: in memory, and the space's sqlite files.
STORES = ("memory", "sqlite")

NOTE = "_support.contents.NoteContent"
PLAIN = "_support.contents.PlainContent"


def in_run(plane_id: str, cell_id: str, term: nu.Nu) -> nu.Nu:
    """``term`` as a program in a run: rerooted as the kernel does at load, one commit to States."""
    return ops.atomic_state(Reroot(plane_id, cell_id)(term))


# --- A kind --------------------------------------------------------------------------------


def test_a_kind_is_its_importable_name_and_its_schema_comes_off_the_generic():
    assert kind_name(NoteContent) == NOTE
    assert load_kind(NOTE) is NoteContent
    assert NoteContent.schema() is Note
    assert PlainContent.schema() is Note

    class Deeper(NoteContent):
        pass

    assert Deeper.schema() is Note
    assert (NoteContent.title(), PlainContent.title()) == ("Note", "Plain")


def test_a_kind_with_no_schema_and_a_name_that_is_not_a_kind_are_refused():
    with pytest.raises(TypeError, match="names no schema"):
        nuspace.Content.schema()
    with pytest.raises(TypeError, match="not a kind"):
        load_kind("_support.contents.Note")
    with pytest.raises(ImportError):
        load_kind("nowhere_at_all.Kind")


def test_the_form_is_generated_from_match_keywords():
    assert NoteContent.form() == (
        SearchField("text", "text", "Text"),
        SearchField("min_stars", "number", "Min stars"),
        SearchField("done", "switch", "Done"),
    )
    assert PlainContent.form() == ()
    assert content.info(NoteContent) == {
        "label": "Note",
        "fields": [
            {"name": "text", "input": "text", "label": "Text"},
            {"name": "min_stars", "input": "number", "label": "Min stars"},
            {"name": "done", "input": "switch", "label": "Done"},
        ],
    }


def test_a_kind_can_write_its_own_form():
    class Asked(nuspace.Content[Note]):
        @classmethod
        def form(cls):
            return (SearchField("text", "text", "Words"),)

    assert content.info(Asked)["fields"] == [{"name": "text", "input": "text", "label": "Words"}]


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


def test_extensions_register_kinds_by_name_first_wins():
    first = Extension(contents=(NoteContent, PlainContent), name="first")
    second = Extension(contents=(NoteContent,), name="second")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        reg = Registry.merge([first, second])
    assert dict(reg.contents) == {NOTE: NoteContent, PLAIN: PlainContent}
    assert any(issubclass(w.category, RegistryWarning) for w in caught)


def test_loose_kinds_come_ahead_of_extensions():
    reg = space_registry(
        contents=(PlainContent,),
        extensions=[Extension(contents=(NoteContent,))],
        discover=False,
    )
    assert list(reg.contents) == [PLAIN, NOTE]


async def test_open_writes_every_kind_with_its_fields_to_space_info(store):
    await store.run(home.write_info(None, [NoteContent]))
    await store.run(home.write_info(None, [PlainContent, NoteContent]))
    info = await store.read(Space.state.info.contents.extract())
    assert info == {NOTE: content.info(NoteContent), PLAIN: {"label": "Plain", "fields": []}}
