"""Content kinds: name, schema, form and match; where a kind's items sit; finding them.

A kind has no accessors of its own: :func:`entries` is the one spelling of
where its items sit at a place, the same path a ``with_parent`` chain under
``State.content_*`` reaches.
"""

from __future__ import annotations

import pytest
from _support.contents import Note, NoteContent, PlainContent, write
from _support.specs import CONTENTS

import nu
import nustd.kv
from nu.lang import is_null
from nuspace.shapes import State
from nuspace.shapes.content import (
    CELL,
    PLANE,
    SPACE,
    Content,
    SearchField,
    entries,
    kind_name,
    scopes,
)
from nuspace.specs import content_spec


#: Run on both backends: in memory, and the space's sqlite files.
STORES = ("memory", "sqlite")

NOTE = "testing.Note"
PLAIN = "testing.Plain"
NOTE_SPEC, PLAIN_SPEC = CONTENTS


# --- A kind --------------------------------------------------------------------------------


def test_a_kind_is_its_declared_name_and_its_schema_comes_off_the_generic():
    assert (NoteContent.name, kind_name(NoteContent)) == ("Note", NOTE)
    assert content_spec(NOTE) is NOTE_SPEC
    assert NoteContent.schema() is Note
    assert PlainContent.schema() is Note

    class Deeper(NoteContent, name="Deeper"):
        pass

    assert Deeper.schema() is Note


def test_a_kind_with_no_schema_or_no_name_is_refused():
    with pytest.raises(TypeError, match="names no schema"):
        Content.schema()
    with pytest.raises(TypeError, match="declares no name"):

        class Nameless(Content[Note]):
            pass

    with pytest.raises(ValueError, match="no dots"):

        class Dotted(Content[Note], name="a.b"):
            pass


def test_a_kind_has_no_scope_accessors():
    for gone in ("cell", "plane", "space", "at", "items", "new"):
        assert not hasattr(NoteContent, gone)


def test_the_form_is_generated_from_match_keywords():
    assert NoteContent.form() == (
        SearchField("text", "text", "Text"),
        SearchField("min_stars", "number", "Min stars"),
        SearchField("done", "switch", "Done"),
    )
    assert PlainContent.form() == ()


def test_defaults_match_everything_and_draw_nothing():
    item = entries(PlainContent, SPACE)["x"]
    assert nu.run(PlainContent.match(item))[0] is True
    assert isinstance(PlainContent.render(item), nu.Noop)
    assert isinstance(PlainContent.render_hit(item), nu.Noop)


def test_match_branches_on_what_was_asked_at_construction():
    item = entries(NoteContent, SPACE)["x"]
    asked = NoteContent.match(item, text="a")
    both = NoteContent.match(item, text="a", done=True)
    assert nu.tree.size(asked) < nu.tree.size(both)


# --- Where items sit ---------------------------------------------------------------------------


def test_entries_are_typed_as_the_kinds_shape_under_state():
    for level, scope_id in ((CELL, "c"), (PLANE, "p"), (SPACE, "")):
        item = entries(NoteContent, level, scope_id)["x"]
        assert isinstance(item, nustd.kv.ShapeRef)
        assert isinstance(item.body, nustd.kv.StrRef)
        assert isinstance(item.stars, nustd.kv.FloatRef)
        assert nu.shape.root_shape(item.body) is State
    by_name = entries("elsewhere.Note", CELL, "c", schema=Note)["x"]
    assert isinstance(by_name.body, nustd.kv.StrRef)
    with pytest.raises(ValueError, match="scope level"):
        entries(NoteContent, "shelf", "s")


async def test_items_sit_by_kind_then_place_then_content_key(store):
    await store.run(
        write(NoteContent, (CELL, "c1"), "a", body="in a cell", stars=2.0)
        >> write(NoteContent, (PLANE, "p1"), "b", body="on a plane")
        >> write(NoteContent, (SPACE, ""), "c", done=True)
        >> write(PlainContent, (CELL, "c1"), "a", body="plain")
    )
    assert await store.read(State.content_cells.extract()) == {
        NOTE: {"cells": {"c1": {"entries": {"a": {"body": "in a cell", "stars": 2.0}}}}},
        PLAIN: {"cells": {"c1": {"entries": {"a": {"body": "plain"}}}}},
    }
    assert await store.read(State.content_planes.extract()) == {
        NOTE: {"planes": {"p1": {"entries": {"b": {"body": "on a plane"}}}}}
    }
    assert await store.read(State.content_space.extract()) == {
        NOTE: {"entries": {"c": {"done": True}}}
    }
    # The same item through a program's own chain, placed with with_parent.
    placed = Note.body.with_parent(State.content_cells[NOTE].cells["c1"].entries["a"])
    assert await store.read(placed) == "in a cell"


async def test_entries_list_and_remove_one_place(store):
    await store.run(
        write(NoteContent, (CELL, "c1"), "a", body="one")
        >> write(NoteContent, (CELL, "c1"), "b", body="two")
        >> write(NoteContent, (CELL, "c2"), "a", body="elsewhere")
    )
    held = entries(NoteContent, CELL, "c1")
    assert sorted(await store.read(nu.list(held.keys()))) == ["a", "b"]
    assert await store.read(held["b"].body) == "two"
    assert await store.read(entries(NoteContent, PLANE, "p").exists()) is False
    assert is_null(await store.read(entries(NoteContent, PLANE, "p")["x"].body))
    await store.run(nustd.kv.atomic(held["a"].erase()))
    assert await store.read(nu.list(held.keys())) == ["b"]


# --- Finding -----------------------------------------------------------------------------------


async def test_find_walks_cells_then_planes_then_the_space(store):
    await store.run(
        write(NoteContent, (SPACE, ""), "s", body="basil in the space")
        >> write(NoteContent, (PLANE, "p"), "t", body="basil on a plane", stars=4.0)
        >> write(NoteContent, (CELL, "c"), "a", body="basil in a cell", stars=1.0)
        >> write(NoteContent, (CELL, "c"), "b", body="mint")
        >> write(PlainContent, (CELL, "c"), "a", body="basil, another kind")
    )
    found = await store.read(NoteContent.find(text="basil"))
    assert [(a["kind"], list(a["scope"]), a["key"]) for a, _ in found] == [
        (NOTE, [CELL, "c"], "a"),
        (NOTE, [PLANE, "p"], "t"),
        (NOTE, [SPACE, ""], "s"),
    ]
    assert found[0][1] == {"body": "basil in a cell", "stars": 1.0}
    both = await store.read(NoteContent.find(text="basil", min_stars=2))
    assert [a["key"] for a, _ in both] == ["t"]
    assert len(await store.read(NoteContent.find())) == 4
    with pytest.raises(TypeError):
        PlainContent.find(text="basil")


async def test_scopes_list_only_the_places_holding_the_kind(store):
    assert await store.read(scopes(NoteContent, CELL)) == []
    await store.run(write(NoteContent, (CELL, "c1"), "a", body="x"))
    assert await store.read(scopes(NoteContent, CELL)) == ["c1"]
    assert await store.read(scopes(PlainContent, CELL)) == []
    with pytest.raises(ValueError, match="scope level"):
        scopes(NoteContent, SPACE)
