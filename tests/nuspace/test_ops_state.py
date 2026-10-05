"""State ops: a sibling's state, wiping and dropping state in its own store, and the extension ops."""

from __future__ import annotations

import asyncio

import pytest
from _support.made import MADE

import nu
import nustd.kv
from nuspace import ops
from nuspace.ops.plane import plane_icon
from nuspace.ops.state import drop_cell_state, drop_plane_state
from nuspace.ops.utils import atomic_state
from nuspace.shapes import ROOT, CellState, PlaneState, Space, States, reroot


#: Run on both backends: in memory, and the space's sqlite files.
STORES = ("memory", "sqlite")


class Tick(CellState):
    n = nustd.kv.IntRef.slot()


class Chat(PlaneState):
    title = nustd.kv.StrRef.slot()


def cell_state(p, c):
    return States.planes[p].cells[c]


def plane_state(p):
    return States.planes[p].state


def in_run(plane_id, cell_id, term):
    """``term`` as a program in a run: rerooted, its plane in a frame, one commit to States."""
    body = reroot(term, ops.Here.plane, cell_id)
    return nu.Frame(ops.Here, nustd.kv.Transaction(body, scope=States), plane=plane_id)


async def seeded(store):
    """A plane with cells ``a`` and ``b``, each with state, and the plane's shared state."""
    p = await store.made(ops.add_plane(backend="async", into=MADE))
    a = await store.made(ops.add_cell(p, "a", into=MADE))
    b = await store.made(ops.add_cell(p, "b", into=MADE))
    await store.run(in_run(p, a, Tick.n.set(1) >> Chat.title.set("t")))
    await store.run(in_run(p, b, Tick.n.set(2)))
    return p, a, b


async def test_state_lands_in_the_state_store_by_plane_and_cell(store):
    p, a, b = await seeded(store)
    assert await store.read(States.planes[p].extract()) == {
        "state": {"title": "t"},
        "cells": {a: {"n": 1}, b: {"n": 2}},
    }
    # Space holds structure only: no state under the plane or its cells.
    assert not await store.read(Space.planes[p].contains("state"))
    assert not await store.read(Space.planes[p].cells[a].contains("state"))


async def test_two_cells_state_is_their_own(store):
    p, a, b = await seeded(store)
    await store.run(in_run(p, a, Tick.n.set(Tick.n + 10)))
    assert await store.read(reroot(Tick.n, p, a)) == 11
    assert await store.read(reroot(Tick.n, p, b)) == 2


async def test_sibling_lands_under_the_sibling_cell(store):
    p = await store.made(ops.add_plane(backend="async", into=MADE))
    a = await store.made(ops.add_cell(p, "a", into=MADE))
    b = await store.made(ops.add_cell(p, "b", into=MADE))
    term = Tick.n.set(1) >> ops.sibling(b, Tick.n.set(7)) >> Chat.title.set("t")
    await store.run(in_run(p, a, term))
    assert await store.read(cell_state(p, a).extract()) == {"n": 1}
    assert await store.read(cell_state(p, b).extract()) == {"n": 7}
    assert await store.read(plane_state(p).extract()) == {"title": "t"}


async def test_sibling_reads(store):
    p = await store.made(ops.add_plane(backend="async", into=MADE))
    a = await store.made(ops.add_cell(p, "a", into=MADE))
    b = await store.made(ops.add_cell(p, "b", into=MADE))
    await store.run(in_run(p, b, Tick.n.set(5)))
    await store.run(in_run(p, a, Tick.n.set(ops.sibling(b, Tick.n) + 1)))
    assert await store.read(reroot(Tick.n, p, a)) == 6


def test_sibling_leaves_plane_state_and_foreign_chains_alone():
    term = Chat.title.set("x") >> Space.planes["p"].name.set("y")
    assert ops.sibling("b", term) is term


# --- bracketed: the hands off brackets ---------------------------------------------


def here(plane_id, cell_id, term):
    """``term`` with the frame the kernel holds around a run, and nothing else."""
    return nu.Frame(ops.Here, term, plane=plane_id, cell=cell_id)


async def test_bracketed_lands_state_under_the_running_cell_and_commits_each_step(store):
    p = await store.made(ops.add_plane(backend="async", into=MADE))
    a = await store.made(ops.add_cell(p, "a", into=MADE))
    steps = Tick.n.set(1) >> Tick.n.set(Tick.n + 1) >> Chat.title.set(nu.ToStr(Tick.n))
    await store.run(here(p, a, ops.bracketed(steps)))
    assert await store.read(cell_state(p, a).extract()) == {"n": 2}
    assert await store.read(plane_state(p).extract()) == {"title": "2"}


async def test_bracketed_reads_and_writes_both_stores(store):
    """A step that reads Space and writes States gets a bracket of each."""
    p = await store.made(ops.add_plane(backend="async", name="notes", into=MADE))
    a = await store.made(ops.add_cell(p, "a", into=MADE))
    term = ops.rename_plane(p, "ideas") >> Chat.title.set(Space.planes[p].name)
    await store.run(here(p, a, ops.bracketed(term)))
    assert await store.read(plane_state(p).extract()) == {"title": "ideas"}


async def test_the_kernel_reroot_leaves_a_bracketed_term_where_it_landed(store):
    """Rerooted through ``Here`` by the helper, the chains no longer root at
    ``CellState``, so the kernel's own reroot, run after, moves nothing."""
    p = await store.made(ops.add_plane(backend="async", into=MADE))
    a = await store.made(ops.add_cell(p, "a", into=MADE))
    b = await store.made(ops.add_cell(p, "b", into=MADE))
    landed = ops.bracketed(Tick.n.set(3))
    assert reroot(landed, p, b) is landed
    await store.run(here(p, a, reroot(landed, p, b)))
    assert await store.read(cell_state(p, a).extract()) == {"n": 3}
    assert await store.read(nu.list(States.planes[p].cells.keys())) == [a]


def test_bracketed_keeps_an_ops_own_bracket_and_brackets_a_loop_per_step():
    op = ops.add_plane("p", backend="async")
    assert ops.bracketed(op) is op
    loop = nu.ForeverDo(nu.DelayedDo(1.0, Tick.n.set(Tick.n.fallback(0) + 1)))
    assert isinstance(ops.bracketed(loop), nu.ForeverDo)


async def test_clear_state(store):
    p, a, b = await seeded(store)
    await store.run(ops.clear_state(p, a))
    assert await store.read(cell_state(p, a).extract()) == {}
    assert await store.read(cell_state(p, b).extract()) == {"n": 2}
    assert await store.read(plane_state(p).extract()) == {"title": "t"}
    await store.run(ops.clear_state(p))
    assert await store.read(plane_state(p).extract()) == {}
    assert await store.read(cell_state(p, b).extract()) == {"n": 2}
    await store.run(ops.clear_state("nope") >> ops.clear_state(p, "nope"))
    assert await store.read(ops.planes()) == [p]
    assert await store.read(ops.cells(p)) == [a, b]
    # Nothing is written for a plane or cell that is not there.
    assert await store.read(nu.list(States.planes.keys())) == [p]
    assert await store.read(nu.list(States.planes[p].cells.keys())) == [b]


async def test_clear_state_of_a_plane_with_none_writes_nothing(store):
    p = await store.made(ops.add_plane(backend="async", into=MADE))
    c = await store.made(ops.add_cell(p, "c", into=MADE))
    await store.run(ops.clear_state(p) >> ops.clear_state(p, c))
    assert await store.read(nu.list(States.planes.keys())) == []


async def test_remove_cell_drops_its_state_only(store):
    p, a, b = await seeded(store)
    await store.run(ops.remove_cell(p, a))
    assert await store.read(ops.cells(p)) == [b]
    assert await store.read(States.planes[p].extract()) == {
        "state": {"title": "t"},
        "cells": {b: {"n": 2}},
    }


async def test_remove_plane_drops_its_state_and_its_cells_and_below(store):
    p, _, _ = await seeded(store)
    q = await store.made(ops.add_plane(parent=p, backend="async", into=MADE))
    c = await store.made(ops.add_cell(q, "c", into=MADE))
    await store.run(in_run(q, c, Tick.n.set(3)))
    other, keep, _ = await seeded(store)
    await store.run(ops.remove_plane(p))
    assert not await store.read(ops.plane_exists(p))
    assert await store.read(nu.list(States.planes.keys())) == [other]
    assert await store.read(reroot(Tick.n, other, keep)) == 1
    # Gone already: nothing more to drop.
    await store.run(ops.remove_plane(p))
    assert await store.read(nu.list(States.planes.keys())) == [other]


async def test_a_refused_remove_plane_keeps_state(store):
    p, a, _ = await seeded(store)
    await store.run(ops.add_plane("sys", system=True, parent=p, backend="async"))
    await store.run(ops.remove_plane(p))
    assert await store.read(ops.plane_exists(p))
    assert await store.read(reroot(Tick.n, p, a)) == 1


async def test_dropping_state_spares_a_cell_that_is_there(store):
    """Run after the structure commit, the drop leaves a cell given its id again alone."""
    p, a, _ = await seeded(store)
    await store.run(atomic_state(drop_cell_state(p, a) >> drop_plane_state(p)))
    assert await store.read(reroot(Tick.n, p, a)) == 1
    assert await store.read(reroot(Chat.title, p, a)) == "t"


# --- extend ---------------------------------------------------------------------


async def test_create_plane_seeds_cells_and_nested_children(store):
    leaf = ops.Plane("leaf", "Leaf", cells=(("note", "n"),), backend="mp")
    mid = ops.Plane("mid", "Mid", meta={"editable": True}, children=(leaf,), backend="async")
    spec = ops.Plane(
        "tracker",
        "Tracker",
        icon="list",
        meta={"k": 1},
        cells=(("form", "f"), ("list", "l")),
        children=(mid, leaf),
        backend="mp",
    )
    top = await store.made(ops.add_plane(name="top", backend="async", into=MADE))
    made = await store.made(ops.create_plane(spec, parent=top, into=MADE))
    assert await store.read(ops.children(top)) == [made]
    rows = {r["id"]: r for r in await store.read(ops.plane_rows())}
    assert (rows[made]["name"], rows[made]["meta"]) == (
        "Tracker",
        {"k": 1, "icon": "lucide:list"},
    )
    assert rows[made]["props"] == {
        "system": False,
        "ui": True,
        "made_by": "tracker",
        "backend": "mp",
    }
    assert [(c["name"], c["prog"]) for c in await store.read(ops.cell_rows(made))] == [
        ("form", "f"),
        ("list", "l"),
    ]
    m, lone = await store.read(ops.children(made))
    assert [rows[m]["name"], rows[lone]["name"]] == ["Mid", "Leaf"]
    assert rows[m]["meta"] == {"editable": True}
    (deep,) = await store.read(ops.children(m))
    assert rows[deep]["props"]["made_by"] == "leaf"
    assert [c["name"] for c in await store.read(ops.cell_rows(deep))] == ["note"]
    # Each runs on its own spec's backend.
    backends = [rows[pid]["props"]["backend"] for pid in (m, lone, deep)]
    assert backends == ["async", "mp", "mp"]


async def test_create_plane_runs_on_its_specs_backend(store):
    made = await store.made(ops.create_plane(ops.Plane("j", "J", backend="mp"), into=MADE))
    assert await store.read(Space.planes[made].props.backend) == "mp"


async def test_create_plane_is_seen_whole_or_not_at_all(store):
    prog = "def out():\n    return nu.Noop()\n"
    kid = ops.Plane("kid", "Kid", cells=(("c", prog),), backend="async")
    spec = ops.Plane("t", "T", cells=(("a", prog), ("b", prog)), children=(kid,), backend="async")
    shape = nu.Dict.of(
        planes=nu.Len(ops.plane_rows()),
        cells=nu.Len(ops.cells("p1")),
        children=nu.Len(ops.children("p1")),
    )
    seen, making = [], True

    async def reader() -> None:
        while making:
            seen.append(tuple((await store.read(shape)).values()))
            await asyncio.sleep(0)

    reading = asyncio.create_task(reader())
    await asyncio.sleep(0)
    await store.run(ops.create_plane(spec, plane_id="p1"))
    making = False
    await reading
    seen.append(tuple((await store.read(shape)).values()))
    # Nothing, or the plane with both cells and its child: never a plane half made.
    assert set(seen) <= {(0, 0, 0), (2, 2, 1)}
    assert seen[-1] == (2, 2, 1)


def test_plane_spec_requires_a_backend():
    with pytest.raises(TypeError, match="backend"):
        ops.Plane("x", "X")  # type: ignore[call-arg]
    with pytest.raises(ValueError, match="backend is required"):
        ops.Plane("x", "X", backend="")


async def test_add_plane_refuses_an_empty_backend(store):
    with pytest.raises(ValueError, match="needs a backend"):
        ops.add_plane("p", backend="")
    # A term that yields "" is refused when it runs, before the commit writes.
    with pytest.raises(ValueError, match="needs a backend"):
        await store.run(ops.add_plane("p", backend=nu.ToStr(nu.Str(""))))
    assert await store.read(ops.plane_rows()) == []


async def test_create_plane_name_and_id(store):
    plain = ops.Plane("plain", "Plain", backend="async")
    assert await store.made(ops.create_plane(plain, name="Notes", plane_id="p1", into=MADE)) == "p1"
    (row,) = await store.read(ops.plane_rows())
    assert (row["name"], row["parent"]) == ("Notes", ROOT)
    assert await store.read(ops.cells("p1")) == []
    # A term built once creates a new plane each time it runs.
    term = ops.create_plane(plain, into=MADE)
    assert await store.made(term) != await store.made(term)


async def test_create_plane_writes_the_icon(store):
    emoji = ops.Plane("e", "E", icon="emoji:\U0001f4da", backend="async")
    kept = ops.Plane("k", "K", icon="list", meta={"icon": "emoji:\U0001f331"}, backend="async")
    blank = ops.Plane("b", "B", icon="list", meta={"icon": ""}, backend="async")
    for spec in (emoji, kept, blank):
        await store.run(ops.create_plane(spec, plane_id=spec.name))
    meta = {r["id"]: r["meta"] for r in await store.read(ops.plane_rows())}
    assert meta["e"] == {"icon": "emoji:\U0001f4da"}
    # A spec's meta that names an icon wins, even an empty one.
    assert meta["k"] == {"icon": "emoji:\U0001f331"}
    assert meta["b"] == {"icon": ""}
    with pytest.raises(ValueError, match="neither"):
        ops.create_plane(ops.Plane("x", "X", icon="svg:x", backend="async"))


async def test_set_plane_icon(store):
    p = await store.made(ops.add_plane(meta={"editable": True}, backend="async", into=MADE))
    await store.run(ops.set_plane_icon(p, "folder"))
    await store.run(ops.set_plane_icon("missing", "folder"))
    (row,) = await store.read(ops.plane_rows())
    # A bare name is a lucide one, and the rest of meta stays.
    assert row["meta"] == {"editable": True, "icon": "lucide:folder"}
    await store.run(ops.set_plane_icon(p, nu.Str("emoji:\u2728")))
    assert (await store.read(ops.plane_rows()))[0]["meta"]["icon"] == "emoji:\u2728"
    await store.run(ops.set_plane_icon(p, ""))
    assert (await store.read(ops.plane_rows()))[0]["meta"] == {"editable": True, "icon": ""}


def test_plane_icon_spelling():
    assert plane_icon(" folder ") == "lucide:folder"
    assert plane_icon("lucide:cpu") == "lucide:cpu"
    assert plane_icon("emoji:\U0001f680") == "emoji:\U0001f680"
    assert plane_icon("") == ""
    for bad in ("emoji:", "lucide: ", "img:x"):
        with pytest.raises(ValueError):
            plane_icon(bad)


async def test_insert_snippet(store):
    p = await store.made(ops.add_plane(backend="async", into=MADE))
    first = await store.made(ops.add_cell(p, "x", into=MADE))
    snippet = ops.Snippet("ticker", "Ticker", "def out(): ...")
    c = await store.made(ops.insert_snippet(p, snippet, index=0, into=MADE))
    assert await store.read(ops.cells(p)) == [c, first]
    assert (await store.read(ops.cell_rows(p)))[0] == {
        "id": c,
        "name": "ticker",
        "prog": "def out(): ...",
        "props": {"made_by": "ticker", "has_ui": False},
        "meta": {},
    }


async def test_snippet_cell_meta_stays_free(store):
    """``made_by`` is a prop: a cell's meta takes the same key without touching it."""
    p = await store.made(ops.add_plane(backend="async", into=MADE))
    c = await store.made(ops.insert_snippet(p, ops.Snippet("ticker", "Ticker", ""), into=MADE))
    await store.run(ops.set_cell_meta(p, c, {"made_by": "x", "k": 1}))
    row = (await store.read(ops.cell_rows(p)))[0]
    assert row["props"] == {"made_by": "ticker", "has_ui": False}
    assert row["meta"] == {"made_by": "x", "k": 1}
