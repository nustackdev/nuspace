"""``nuspace.state``: the clears, each scope wiped on its own."""

from __future__ import annotations

import pytest
from _support.contents import NoteContent

import nu
import nuspace
import nustd.kv
from nuspace.errors import Missing
from nuspace.shapes import State


STORES = ("memory", "sqlite")

at = nuspace.at


class Counter(nu.Shape):
    value = nustd.kv.IntRef.slot()


async def do(store, term):
    return await store.run(nuspace.atomic(term))


@pytest.fixture
async def kept(store):
    """Plane ``p`` with cells ``c1``, ``c2``, each scope holding a slot and a note."""
    await do(
        store,
        nuspace.plane.add("p", backend="async")
        >> nuspace.cell.add("p", "s", id="c1")
        >> nuspace.cell.add("p", "s", id="c2"),
    )
    writes = [
        at.space.state(Counter).value.set(9),
        at.space.content(NoteContent)["n"].body.set("s"),
    ]
    for place in (at.cell(id="c1"), at.cell(id="c2"), at.plane(id="p")):
        writes += [place.state(Counter).value.set(1), place.content(NoteContent)["n"].body.set("x")]
    await do(store, nu.Sequential(*writes))
    return store


async def held(store, place):
    return await store.read(
        nu.List.of(
            place.state(Counter).value.fallback(0),
            place.content(NoteContent)["n"].body.fallback(""),
        )
    )


async def test_clear_cell_wipes_its_slots_and_items_only(kept):
    store = kept
    await do(store, nuspace.state.clear_cell("c1"))
    assert await held(store, at.cell(id="c1")) == [0, ""]
    assert await held(store, at.cell(id="c2")) == [1, "x"]
    assert await held(store, at.plane(id="p")) == [1, "x"]
    # A cleared cell starts over: it writes as on a first run.
    await do(store, at.cell(id="c1").state(Counter).value.set(5))
    assert await held(store, at.cell(id="c1")) == [5, ""]


async def test_clear_plane_leaves_its_cells_state(kept):
    store = kept
    await do(store, nuspace.state.clear_plane("p"))
    assert await held(store, at.plane(id="p")) == [0, ""]
    assert await held(store, at.cell(id="c1")) == [1, "x"]


async def test_clear_space_empties_the_space_scope(kept):
    store = kept
    await do(store, nuspace.state.clear_space())
    assert await held(store, at.space) == [0, ""]
    assert await store.read(State.space.extract()) == {}
    assert await held(store, at.cell(id="c1")) == [1, "x"]


async def test_clears_raise_on_a_missing_row_and_work_on_a_removed_one(kept):
    store = kept
    with pytest.raises(Missing):
        await do(store, nuspace.state.clear_cell("nope"))
    with pytest.raises(Missing):
        await do(store, nuspace.state.clear_plane("nope"))
    await do(store, nuspace.cell.remove("c2"))
    await do(store, nuspace.state.clear_cell("c2"))
    assert await held(store, at.cell(id="c2")) == [0, ""]
