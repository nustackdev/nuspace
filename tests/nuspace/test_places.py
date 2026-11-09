"""Places: ``nuspace.at`` and ``nuspace.here`` build the State refs, by scope and whose.

A place reads nothing: what it builds is plain nu on kv refs. The bare
forms need Here, bound here with :func:`nuspace.places.inside` as the kernel
binds it around a cell run.
"""

from __future__ import annotations

import pickle

import pytest
from _support.contents import NoteContent

import nu
import nuspace
import nustd.kv
from nu.lang import is_null
from nuspace.places import Here, inside
from nuspace.shapes import Space, State


STORES = ("memory", "sqlite")

at = nuspace.at


class Counter(nu.Shape):
    """A program's own shape, no scope base."""

    value = nustd.kv.IntRef.slot()


class Prefs(nu.Shape):
    theme = nustd.kv.StrRef.slot()


async def do(store, term):
    return await store.run(nuspace.atomic(term))


@pytest.fixture
async def space(store):
    """Plane ``p`` keyed ``team`` with cells ``c1`` keyed ``summary`` and ``c2``."""
    await do(
        store,
        nuspace.plane.add("p", key="team", backend="async")
        >> nuspace.cell.add("p", "s", id="c1", key="summary")
        >> nuspace.cell.add("p", "s", id="c2"),
    )
    return store


async def test_this_cell_and_plane_resolve_through_here(space):
    store = space
    mine = nuspace.here(Counter).value
    shared = at.plane.state(Counter).value
    step = mine.set(mine.fallback(0) + 1) >> shared.set(7)
    await store.run(inside(nuspace.atomic(step), plane="p", cell="c1"))
    await store.run(inside(nuspace.atomic(step), plane="p", cell="c1"))
    assert await store.read(State.cells.extract()) == {"c1": {"value": 2}}
    assert await store.read(State.planes.extract()) == {"p": {"value": 7}}
    # The same bound place, another cell.
    await store.run(inside(nuspace.atomic(step), plane="p", cell="c2"))
    assert await store.read(Counter.value.with_parent(State.cells["c2"])) == 1


async def test_by_id_and_by_key_land_where_with_parent_does(space):
    store = space
    await do(
        store,
        at.cell(id="c2").state(Counter).value.set(3)
        >> at.cell("summary").state(Counter).value.set(4)
        >> at.plane("team").state(Prefs).theme.set("dark")
        >> at.space.state(Prefs).theme.set("light"),
    )
    assert await store.read(Counter.value.with_parent(State.cells["c2"])) == 3
    assert await store.read(Counter.value.with_parent(State.cells["c1"])) == 4
    assert await store.read(Prefs.theme.with_parent(State.planes["p"])) == "dark"
    assert await store.read(Prefs.theme.with_parent(State.space)) == "light"
    assert await store.read(at.plane(id="p").state(Prefs).theme) == "dark"


async def test_a_key_that_finds_nothing_raises_on_read_and_write(space):
    store = space
    gone = at.cell("nobody").state(Counter).value
    with pytest.raises(nustd.kv.NullAddressError):
        await store.read(gone)
    # Where a key may be missing, the caller branches on the index first.
    held = nu.If(nu.IsNull(Space.indexes.cell_keys["nobody"]), 0, gone)
    assert await store.read(held) == 0
    with pytest.raises(nustd.kv.NullAddressError):
        await do(store, gone.set(1))
    with pytest.raises(nustd.kv.NullAddressError):
        await do(store, at.plane("nobody").content(NoteContent)["x"].body.set("x"))


async def test_bare_places_raise_outside_a_cell_run(space):
    store = space
    for ref in (
        at.cell.state(Counter).value,
        at.plane.state(Counter).value,
        nuspace.here(Counter).value,
    ):
        with pytest.raises(LookupError):
            await store.read(ref)
    # The space has no "this": it works anywhere.
    assert is_null(await store.read(at.space.state(Prefs).theme))


async def test_content_is_a_dict_by_content_key_at_each_scope(space):
    store = space
    notes = at.cell("summary").content(NoteContent)
    await do(
        store,
        notes["title"].body.set("hey")
        >> notes["todo"].body.set("water the basil")
        >> at.plane(id="p").content(NoteContent)["readme"].body.set("plane")
        >> at.space.content(NoteContent)["readme"].body.set("space"),
    )
    assert sorted(await store.read(nu.list(notes.keys()))) == ["title", "todo"]
    await do(store, notes["todo"].erase())
    assert await store.read(nu.list(notes.keys())) == ["title"]
    assert await store.read(State.content_cells.extract()) == {
        "testing.Note": {"cells": {"c1": {"entries": {"title": {"body": "hey"}}}}}
    }
    assert await store.read(at.space.content(NoteContent)["readme"].body) == "space"
    # This cell's content, through Here.
    own = at.cell.content(NoteContent)["title"].body
    assert await store.run(inside(nuspace.atomic(own), plane="p", cell="c1")) == "hey"


def test_at_takes_a_key_or_an_id_and_only_the_bare_scope_is_callable():
    with pytest.raises(TypeError, match="exactly one"):
        at.cell()
    with pytest.raises(TypeError, match="exactly one"):
        at.plane("k", id="p")
    with pytest.raises(TypeError):
        at.cell("a")("b")  # type: ignore[operator]
    with pytest.raises(TypeError):
        at.space("x")  # type: ignore[operator]


def test_a_place_is_built_once_and_pickles_as_a_term():
    """Bound at module level, a place goes to a worker with the program."""
    term = at.cell.state(Counter).value.set(1) >> at.cell("summary").content(NoteContent)[
        "t"
    ].body.set("x")
    assert isinstance(pickle.loads(pickle.dumps(term)), nu.Nu)  # noqa: S301 -- our own term


def test_inside_binds_the_ids_here_holds():
    read = nu.List.of(Here.plane, Here.cell, Here.plane_run, Here.cell_run)
    held = inside(read, plane="p", cell="c", plane_run="r", cell_run="cr")
    assert nu.run(held)[0] == ["p", "c", "r", "cr"]


async def test_a_key_place_inside_atomic_reads_space_from_a_snapshot(space):
    """One State commit: the key is read from Space, nothing is written there."""
    store = space
    await do(store, at.cell("summary").state(Counter).value.set(1))
    term = nuspace.atomic(at.cell("summary").state(Counter).value.set(2))
    assert isinstance(term, nustd.kv.RetryOnConflict)
    await store.run(term)
    assert (
        await store.read(Counter.value.with_parent(State.cells[Space.indexes.cell_keys["summary"]]))
        == 2
    )
