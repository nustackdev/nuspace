"""Structure ops: planes, cells, the tree, and the reads over them.

Each op is evaluated on its own against one held store, the way a caller
in any process would, then read back.
"""

from __future__ import annotations

import pickle

import nu
import nustd.kv
from nuspace import ops
from nuspace.shapes import ROOT, STATUS_STOPPING, Space


async def plane(store, name="", **kw):
    return await store.run(ops.add_plane(name=name, **kw))


async def cell(store, plane_id, prog="def out(): pass", **kw):
    return await store.run(ops.add_cell(plane_id, prog, **kw))


NO_PROPS = {"system": False, "ui": False, "made_by": ""}


# --- Planes --------------------------------------------------------------------


async def test_add_plane_writes_the_row_and_links_under_root(store):
    p = await plane(store, "notes", ui=True, made_by="page", meta={"editable": True})
    assert p.startswith("p_")
    assert await store.read(ops.planes()) == [p]
    assert await store.read(ops.plane_exists(p)) is True
    assert await store.read(ops.cells(p)) == []
    assert await store.read(ops.children()) == [p]
    assert await store.read(ops.parent(p)) == ROOT
    assert await store.read(ops.plane_rows()) == [
        {
            "id": p,
            "name": "notes",
            "props": {"system": False, "ui": True, "made_by": "page"},
            "meta": {"editable": True},
            "parent": ROOT,
        }
    ]


async def test_add_plane_mints_at_evaluation(store):
    term = ops.add_plane(name="x")
    a, b = await store.run(term), await store.run(term)
    assert a != b
    again = pickle.loads(pickle.dumps(term))  # noqa: S301
    c = await store.run(again)
    assert await store.read(ops.planes()) == [a, b, c]


async def test_add_plane_given_id_and_parent(store):
    top = await plane(store, "top")
    assert await store.run(ops.add_plane("kid", parent=top, system=True)) == "kid"
    assert await store.read(ops.children(top)) == ["kid"]
    assert await store.read(ops.children()) == [top]
    assert await store.read(ops.parent("kid")) == top
    orphan = await store.run(ops.add_plane(parent="nope"))
    assert await store.read(ops.parent(orphan)) == ROOT


async def test_yielding_ops_chain_and_bind(store):
    """A yielding op is an Action: ``>>`` takes it, ``nu.Let`` binds it."""
    pid = nu.StrAttrRef("p")
    term = ops.add_plane(name="a") >> nu.Let(
        "p", ops.add_plane(name="b"), ops.add_cell(pid, "src", name="c")
    )
    await store.run(term)
    rows = await store.read(ops.plane_rows())
    assert [r["name"] for r in rows] == ["a", "b"]
    assert await store.read(nu.List(ops.cell_rows(rows[1]["id"]))) == [
        {
            "id": (await store.read(ops.cells(rows[1]["id"])))[0],
            "name": "c",
            "prog": "src",
            "meta": {},
        }
    ]


async def test_rename_plane(store):
    p = await plane(store, "a")
    await store.run(ops.rename_plane(p, "b") >> ops.rename_plane("nope", "c"))
    assert [r["name"] for r in await store.read(ops.plane_rows())] == ["b"]
    assert await store.read(ops.planes()) == [p]


async def test_set_plane_meta_merges(store):
    p = await plane(store, made_by="page", meta={"a": 1, "b": 2})
    await store.run(ops.set_plane_meta(p, {"b": 3, "c": {"d": 4}, "made_by": "x"}))
    (row,) = await store.read(ops.plane_rows())
    assert row["meta"] == {"a": 1, "b": 3, "c": {"d": 4}, "made_by": "x"}
    # A meta key named like a prop is only meta.
    assert row["props"] == {"system": False, "ui": False, "made_by": "page"}


async def test_add_plane_again_rewrites_props_and_merges_meta(store):
    p = await plane(store, system=True, ui=True, made_by="a", meta={"x": 1})
    await store.run(ops.add_plane(p, name="b", made_by="b", meta={"y": 2}))
    (row,) = await store.read(ops.plane_rows())
    assert row["props"] == {"system": False, "ui": False, "made_by": "b"}
    assert row["meta"] == {"x": 1, "y": 2}


async def test_remove_plane_drops_it_and_its_subtree(store):
    top, keep = await plane(store, "top"), await plane(store, "keep")
    mid = await store.run(ops.add_plane(parent=top))
    leaf = await store.run(ops.add_plane(parent=mid))
    await cell(store, leaf)
    assert await store.run(ops.remove_plane(top)) is True
    assert await store.read(ops.planes()) == [keep]
    assert await store.read(ops.children()) == [keep]
    assert await store.read(nu.list(Space.tree.keys())) == [ROOT]
    assert await store.read(ops.cells(leaf)) == []


async def test_remove_plane_refuses_system(store):
    svc = await store.run(ops.add_plane(name="init", system=True))
    top = await plane(store)
    await store.run(ops.add_plane(parent=top, system=True))
    assert await store.run(ops.remove_plane(svc)) is False
    assert await store.run(ops.remove_plane(top)) is False
    assert await store.run(ops.remove_plane("nope")) is False
    assert len(await store.read(ops.planes())) == 3


async def test_remove_plane_downs_live_runs(store):
    p, other = await plane(store), await plane(store)
    kid = await store.run(ops.add_plane(parent=p))
    await cell(store, p)
    await cell(store, kid)
    await cell(store, other)
    w = await store.run(ops.worker())
    mine = await store.run(ops.up_plane(p, worker=w))
    below = await store.run(ops.up_plane(kid, worker=w))
    theirs = await store.run(ops.up_plane(other, worker=w))
    assert await store.run(ops.remove_plane(p)) is True
    status = {r["id"]: r["status"] for r in await store.read(ops.runs())}
    assert [status[r] for r in mine + below] == [STATUS_STOPPING] * 2
    assert status[theirs[0]] == "starting"


# --- Cells ---------------------------------------------------------------------


async def test_add_cell_places_by_index(store):
    p = await plane(store)
    a = await cell(store, p, name="a")
    b = await cell(store, p, name="b")
    c = await cell(store, p, name="c", index=0, meta={"k": 1})
    assert c.startswith("c_")
    assert await store.read(ops.cells(p)) == [c, a, b]
    assert await store.read(ops.cell_exists(p, a)) is True
    assert (await store.read(ops.cell_rows(p)))[0] == {
        "id": c,
        "name": "c",
        "prog": "def out(): pass",
        "meta": {"k": 1},
    }


async def test_add_cell_refuses_a_missing_plane(store):
    assert await store.run(ops.add_cell("nope", "src")) == ""
    assert await store.read(ops.planes()) == []


async def test_add_cell_given_id(store):
    p = await plane(store)
    assert await cell(store, p, cell_id="x") == "x"
    assert await cell(store, p, cell_id="x", name="again") == "x"
    assert await store.read(ops.cells(p)) == ["x"]


async def test_cells_lists_unordered_cells_last(store):
    p = await plane(store)
    a = await cell(store, p)
    await store.run(nustd.kv.Transaction(Space.planes[p].cells["stray"].prog.set("s"), scope=Space))
    await store.run(nustd.kv.Transaction(Space.planes[p].order.append("ghost"), scope=Space))
    assert await store.read(ops.cells(p)) == [a, "stray"]


async def test_remove_cell(store):
    p = await plane(store)
    a, b = await cell(store, p), await cell(store, p)
    w = await store.run(ops.worker())
    runs = await store.run(ops.up(p, [a, b], worker=w))
    await store.run(ops.remove_cell(p, a) >> ops.remove_cell(p, "nope"))
    assert await store.read(ops.cells(p)) == [b]
    assert await store.read(ops.cell_exists(p, a)) is False
    status = {r["id"]: r["status"] for r in await store.read(ops.runs())}
    assert status == {runs[0]: STATUS_STOPPING, runs[1]: "starting"}


async def test_rename_cell_and_set_prog(store):
    p = await plane(store)
    a = await cell(store, p, name="a")
    await store.run(ops.rename_cell(p, a, "b") >> ops.set_prog(p, a, "new"))
    await store.run(ops.set_prog(p, "nope", "x"))
    assert await store.read(ops.prog(p, a)) == "new"
    assert await store.read(ops.prog(p, "nope")) == ""
    assert await store.read(ops.cells(p)) == [a]
    assert (await store.read(ops.cell_rows(p)))[0]["name"] == "b"


async def test_set_cell_meta_merges(store):
    p = await plane(store)
    a = await cell(store, p, meta={"x": 1})
    await store.run(ops.set_cell_meta(p, a, {"y": 2}))
    assert (await store.read(ops.cell_rows(p)))[0]["meta"] == {"x": 1, "y": 2}


async def test_reorder_cells(store):
    p = await plane(store)
    a, b, c = [await cell(store, p) for _ in range(3)]
    await store.run(ops.reorder_cells(p, [c, "ghost", a]))
    assert await store.read(ops.cells(p)) == [c, a, b]
    await store.run(ops.reorder_cells(p, nu.List.of(b)))
    assert await store.read(ops.cells(p)) == [b, c, a]


async def test_move_cell_keeps_id_and_state(store):
    p, q = await plane(store), await plane(store)
    a = await cell(store, p, name="a")
    q1 = await cell(store, q)
    state = Space.planes[p].cells[a].state
    await store.run(nustd.kv.Transaction(state.set_item("n", {"deep": 3}), scope=Space))
    w = await store.run(ops.worker())
    (run,) = await store.run(ops.up(p, [a], worker=w))
    await store.run(ops.move_cell(p, a, q, 0))
    assert await store.read(ops.cells(p)) == []
    assert await store.read(ops.cells(q)) == [a, q1]
    assert (await store.read(ops.cell_rows(q)))[0]["name"] == "a"
    assert await store.read(Space.planes[q].cells[a].state.extract()) == {"n": {"deep": 3}}
    assert (await store.read(ops.runs()))[0]["status"] == STATUS_STOPPING
    assert run


async def test_move_cell_refuses_same_plane_and_missing(store):
    p = await plane(store)
    a = await cell(store, p)
    await store.run(ops.move_cell(p, a, p) >> ops.move_cell(p, a, "nope"))
    assert await store.read(ops.cells(p)) == [a]


# --- Tree ----------------------------------------------------------------------


async def test_nest_and_unnest(store):
    a, b, c = await plane(store), await plane(store), await plane(store)
    assert await store.run(ops.nest(b, a)) is True
    assert await store.run(ops.nest(c, a, 0)) is True
    assert await store.read(ops.children()) == [a]
    assert await store.read(ops.children(a)) == [c, b]
    assert await store.run(ops.unnest(b)) is True
    assert await store.read(ops.children()) == [a, b]
    assert await store.read(ops.children(a)) == [c]
    assert await store.read(ops.parent(c)) == a


async def test_nest_refuses_cycles(store):
    a = await plane(store)
    b = await store.run(ops.add_plane(parent=a))
    c = await store.run(ops.add_plane(parent=b))
    assert await store.run(ops.nest(a, c)) is False
    assert await store.run(ops.nest(a, b)) is False
    assert await store.run(ops.nest(a, a)) is False
    assert await store.run(ops.nest(a, "nope")) is False
    assert await store.run(ops.nest("nope", ROOT)) is False
    assert await store.read(ops.children()) == [a]
    assert await store.read(ops.children(b)) == [c]
    assert await store.run(ops.nest(c, a)) is True
    assert await store.read(ops.children(a)) == [b, c]


async def test_parent_of_an_unlinked_plane(store):
    assert await store.read(ops.parent("nope")) == ""


async def test_structure_round_trips_through_rocksdb(disk):
    """The codec path: nested meta, a moved cell's nested state, order, the tree."""
    p = await disk.run(ops.add_plane(name="p", meta={"a": {"b": 1}}))
    q = await disk.run(ops.add_plane(name="q", parent=p))
    c = await disk.run(ops.add_cell(p, "src", meta={"m": [1, 2]}))
    state = Space.planes[p].cells[c].state
    await disk.run(nustd.kv.Transaction(state.set_item("n", {"deep": [3]}), scope=Space))
    await disk.run(ops.move_cell(p, c, q))
    assert await disk.read(ops.plane_rows()) == [
        {"id": p, "name": "p", "props": NO_PROPS, "meta": {"a": {"b": 1}}, "parent": ROOT},
        {"id": q, "name": "q", "props": NO_PROPS, "meta": {}, "parent": p},
    ]
    assert await disk.read(ops.cell_rows(q)) == [
        {"id": c, "name": "", "prog": "src", "meta": {"m": [1, 2]}}
    ]
    assert await disk.read(Space.planes[q].cells[c].state.extract()) == {"n": {"deep": [3]}}
    assert await disk.run(ops.remove_plane(p)) is True
    assert await disk.read(ops.planes()) == []
