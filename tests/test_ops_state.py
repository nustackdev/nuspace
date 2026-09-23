"""State ops: a sibling's state, wiping state, and the extension ops."""

from __future__ import annotations

import nu
import nustd.kv
from nuspace import ops
from nuspace.shapes import CellState, PlaneState, Space, reroot


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


async def test_run_app_builds_and_runs_its_tree(store):
    def build(title="page"):
        pid = nu.StrAttrRef("app_plane")
        return nu.Let(
            "app_plane",
            ops.add_plane(name=title, meta={"made_by": "page"}),
            ops.add_cell(pid, "src", name="body"),
        )

    app = ops.App("page", "Page", build, description="a page")
    assert app.section is True
    await store.run(ops.run_app(app, title="notes"))
    (row,) = await store.read(ops.plane_rows())
    assert (row["name"], row["meta"]) == ("notes", {"made_by": "page"})
    assert [c["name"] for c in await store.read(ops.cell_rows(row["id"]))] == ["body"]


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
