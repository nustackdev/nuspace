"""State ops: a sibling's state, wiping state, and the extension ops."""

from __future__ import annotations

import pytest

import nu
import nustd.kv
from nuspace import ops
from nuspace.ops.plane import plane_icon
from nuspace.shapes import ROOT, CellState, PlaneState, Space, reroot


class Tick(CellState):
    n = nustd.kv.IntRef.slot()


class Chat(PlaneState):
    title = nustd.kv.StrRef.slot()


def cell_state(p, c):
    return Space.planes[p].cells[c].state


def in_run(plane_id, cell_id, term):
    """``term`` as the kernel would run it: rerooted, the plane attr bound, bracketed."""
    body = reroot(term, nu.StrAttrRef(ops.PLANE_ATTR), cell_id)
    return nu.Let(ops.PLANE_ATTR, nu.Str(plane_id), nustd.kv.Transaction(body, scope=Space))


async def test_sibling_lands_under_the_sibling_cell(store):
    p = await store.run(ops.add_plane())
    a = await store.run(ops.add_cell(p, "a"))
    b = await store.run(ops.add_cell(p, "b"))
    term = Tick.n.set(1) >> ops.sibling(b, Tick.n.set(7)) >> Chat.title.set("t")
    await store.run(in_run(p, a, term))
    assert await store.read(cell_state(p, a).extract()) == {"n": 1}
    assert await store.read(cell_state(p, b).extract()) == {"n": 7}
    assert await store.read(Space.planes[p].state.extract()) == {"title": "t"}


async def test_sibling_reads(store):
    p = await store.run(ops.add_plane())
    a = await store.run(ops.add_cell(p, "a"))
    b = await store.run(ops.add_cell(p, "b"))
    await store.run(in_run(p, b, Tick.n.set(5)))
    await store.run(in_run(p, a, Tick.n.set(ops.sibling(b, Tick.n) + 1)))
    assert await store.read(cell_state(p, a)["n"]) == 6


def test_sibling_leaves_plane_state_and_foreign_chains_alone():
    term = Chat.title.set("x") >> Space.planes["p"].name.set("y")
    assert ops.sibling("b", term) is term


async def test_clear_state(store):
    p = await store.run(ops.add_plane())
    a = await store.run(ops.add_cell(p, "a"))
    b = await store.run(ops.add_cell(p, "b"))
    await store.run(in_run(p, a, Tick.n.set(1) >> Chat.title.set("t")))
    await store.run(in_run(p, b, Tick.n.set(2)))
    await store.run(ops.clear_state(p, a))
    assert await store.read(cell_state(p, a).extract()) == {}
    assert await store.read(cell_state(p, b).extract()) == {"n": 2}
    assert await store.read(Space.planes[p].state.extract()) == {"title": "t"}
    await store.run(ops.clear_state(p))
    assert await store.read(Space.planes[p].state.extract()) == {}
    await store.run(ops.clear_state("nope") >> ops.clear_state(p, "nope"))
    assert await store.read(ops.planes()) == [p]
    assert await store.read(ops.cells(p)) == [a, b]


# --- extend ---------------------------------------------------------------------


async def test_create_plane_seeds_cells_and_nested_children(store):
    leaf = ops.Plane("leaf", "Leaf", cells=(("note", "n"),))
    mid = ops.Plane("mid", "Mid", meta={"editable": True}, children=(leaf,))
    spec = ops.Plane(
        "tracker",
        "Tracker",
        icon="list",
        meta={"k": 1},
        cells=(("form", "f"), ("list", "l")),
        children=(mid, leaf),
    )
    top = await store.run(ops.add_plane(name="top"))
    made = await store.run(ops.create_plane(spec, parent=top))
    assert await store.read(ops.children(top)) == [made]
    rows = {r["id"]: r for r in await store.read(ops.plane_rows())}
    assert (rows[made]["name"], rows[made]["meta"]) == (
        "Tracker",
        {"k": 1, "icon": "lucide:list"},
    )
    assert rows[made]["props"] == {"system": False, "ui": True, "made_by": "tracker"}
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


async def test_create_plane_name_and_id(store):
    plain = ops.Plane("plain", "Plain")
    assert await store.run(ops.create_plane(plain, name="Notes", plane_id="p1")) == "p1"
    (row,) = await store.read(ops.plane_rows())
    assert (row["name"], row["parent"]) == ("Notes", ROOT)
    assert await store.read(ops.cells("p1")) == []
    # A term built once creates a new plane each time it runs.
    term = ops.create_plane(plain)
    assert await store.run(term) != await store.run(term)


async def test_create_plane_writes_the_icon(store):
    emoji = ops.Plane("e", "E", icon="emoji:\U0001f4da")
    kept = ops.Plane("k", "K", icon="list", meta={"icon": "emoji:\U0001f331"})
    blank = ops.Plane("b", "B", icon="list", meta={"icon": ""})
    for spec in (emoji, kept, blank):
        await store.run(ops.create_plane(spec, plane_id=spec.name))
    meta = {r["id"]: r["meta"] for r in await store.read(ops.plane_rows())}
    assert meta["e"] == {"icon": "emoji:\U0001f4da"}
    # A spec's meta that names an icon wins, even an empty one.
    assert meta["k"] == {"icon": "emoji:\U0001f331"}
    assert meta["b"] == {"icon": ""}
    with pytest.raises(ValueError, match="neither"):
        ops.create_plane(ops.Plane("x", "X", icon="svg:x"))


async def test_set_plane_icon(store):
    p = await store.run(ops.add_plane(meta={"editable": True}))
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
    p = await store.run(ops.add_plane())
    first = await store.run(ops.add_cell(p, "x"))
    snippet = ops.Snippet("ticker", "Ticker", "def out(): ...")
    c = await store.run(ops.insert_snippet(p, snippet, index=0))
    assert await store.read(ops.cells(p)) == [c, first]
    assert (await store.read(ops.cell_rows(p)))[0] == {
        "id": c,
        "name": "ticker",
        "prog": "def out(): ...",
        "meta": {},
    }
