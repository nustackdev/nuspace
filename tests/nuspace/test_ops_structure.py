"""Structure ops: planes, cells, nesting, and the reads over them.

Each op is evaluated on its own against one held store, the way a caller
in any process would, then read back.
"""

from __future__ import annotations

import pytest
from _support.made import MADE

import nu
import nustd.kv
from nu.lang import wire
from nuspace import ops
from nuspace.ops.utils import atomic
from nuspace.shapes import Space, States


async def plane(store, name="", backend="async", **kw):
    return await store.made(ops.add_plane(name=name, backend=backend, **kw, into=MADE))


async def cell(store, plane_id, prog="def out(): pass", **kw):
    return await store.made(ops.add_cell(plane_id, prog, **kw, into=MADE))


#: Run on both backends: in memory, and the space's sqlite files.
STORES = ("memory", "sqlite")

NO_PROPS = {"system": False, "ui": False, "made_by": "", "backend": "async"}


# --- Planes --------------------------------------------------------------------


async def test_add_plane_writes_the_row_and_links_at_the_top(store):
    p = await plane(store, "notes", ui=True, made_by="plain", meta={"editable": True})
    assert p.startswith("p_")
    assert await store.read(ops.planes()) == [p]
    assert await store.read(ops.plane_exists(p)) is True
    assert await store.read(ops.cells(p)) == []
    assert await store.read(ops.children()) == [p]
    assert await store.read(ops.parent(p)) == ""
    assert await store.read(ops.plane_rows()) == [
        {
            "id": p,
            "name": "notes",
            "props": {"system": False, "ui": True, "made_by": "plain", "backend": "async"},
            "meta": {"editable": True},
            "parent": "",
        }
    ]


async def test_add_plane_takes_the_backend_it_is_given_and_has_no_default(store):
    with pytest.raises(TypeError, match="backend"):
        ops.add_plane(name="x")  # type: ignore[call-arg]
    p = await plane(store, "x", backend="mp")
    assert await store.read(Space.planes[p].props.backend) == "mp"
    # A plane whose row names none reads back as naming none, not as a default.
    q = await plane(store, "y", backend="mp")
    await store.run(atomic(Space.planes[q].props.backend.set("")))
    (row,) = [r for r in await store.read(ops.plane_rows()) if r["id"] == q]
    assert row["props"]["backend"] == ""


async def test_add_plane_mints_at_evaluation(store):
    term = ops.add_plane(name="x", backend="async", into=MADE)
    a, b = await store.made(term), await store.made(term)
    assert a != b
    again = wire.loads(wire.dumps(term))
    c = await store.made(again)
    assert await store.read(ops.planes()) == [a, b, c]


async def test_add_plane_given_id_and_parent(store):
    top = await plane(store, "top")
    await store.run(ops.add_plane("kid", parent=top, system=True, backend="async"))
    assert await store.read(ops.children(top)) == ["kid"]
    assert await store.read(ops.children()) == [top]
    assert await store.read(ops.parent("kid")) == top
    orphan = await store.made(ops.add_plane(parent="nope", backend="async", into=MADE))
    assert await store.read(ops.parent(orphan)) == ""


async def test_ops_chain_and_write_what_they_made_into_a_ref(store):
    """An op chains with ``>>``, and a minted id lands in the ``into`` ref for the next to read."""

    def made(pid: nu.ObjectRef) -> nu.Nu:
        b = ops.add_plane(name="b", backend="async", into=pid)
        return b >> ops.add_cell(pid, "src", name="c")

    term = ops.add_plane(name="a", backend="async") >> nu.let("", made)
    await store.run(term)
    rows = await store.read(ops.plane_rows())
    assert [r["name"] for r in rows] == ["a", "b"]
    assert await store.read(nu.List(ops.cell_rows(rows[1]["id"]))) == [
        {
            "id": (await store.read(ops.cells(rows[1]["id"])))[0],
            "name": "c",
            "prog": "src",
            "props": {"made_by": "", "has_ui": False},
            "meta": {},
        }
    ]


async def test_rename_plane(store):
    p = await plane(store, "a")
    await store.run(ops.rename_plane(p, "b") >> ops.rename_plane("nope", "c"))
    assert [r["name"] for r in await store.read(ops.plane_rows())] == ["b"]
    assert await store.read(ops.planes()) == [p]


async def test_set_plane_meta_merges(store):
    p = await plane(store, made_by="plain", meta={"a": 1, "b": 2})
    await store.run(ops.set_plane_meta(p, {"b": 3, "c": {"d": 4}, "made_by": "x"}))
    (row,) = await store.read(ops.plane_rows())
    assert row["meta"] == {"a": 1, "b": 3, "c": {"d": 4}, "made_by": "x"}
    # A meta key named like a prop is only meta.
    assert row["props"] == {"system": False, "ui": False, "made_by": "plain", "backend": "async"}


async def test_add_plane_again_rewrites_props_and_merges_meta(store):
    p = await plane(store, system=True, ui=True, made_by="a", meta={"x": 1})
    await store.run(ops.add_plane(p, name="b", made_by="b", meta={"y": 2}, backend="async"))
    (row,) = await store.read(ops.plane_rows())
    assert row["props"] == {"system": False, "ui": False, "made_by": "b", "backend": "async"}
    assert row["meta"] == {"x": 1, "y": 2}


async def test_remove_plane_drops_it_and_its_subtree(store):
    top, keep = await plane(store, "top"), await plane(store, "keep")
    mid = await store.made(ops.add_plane(parent=top, backend="async", into=MADE))
    leaf = await store.made(ops.add_plane(parent=mid, backend="async", into=MADE))
    gone = [await cell(store, top), await cell(store, leaf)]
    kept = await cell(store, keep)
    await store.run(ops.remove_plane(top))
    assert await store.read(ops.planes()) == [keep]
    assert await store.read(ops.children()) == [keep]
    assert not any([await store.read(ops.plane_exists(x)) for x in (mid, leaf)])
    assert await store.read(ops.cells(leaf)) == []
    assert await store.read(nu.list(Space.cells.keys())) == [kept]
    assert not any([await store.read(ops.cell_exists(c)) for c in gone])


async def test_remove_plane_refuses_system(store):
    svc = await store.made(ops.add_plane(name="init", system=True, backend="async", into=MADE))
    top = await plane(store)
    await store.run(ops.add_plane(parent=top, system=True, backend="async"))
    await store.run(ops.remove_plane(svc) >> ops.remove_plane(top) >> ops.remove_plane("nope"))
    assert len(await store.read(ops.planes())) == 3


async def test_remove_plane_kills_live_runs(store):
    p, other = await plane(store), await plane(store)
    kid = await store.made(ops.add_plane(parent=p, backend="async", into=MADE))
    await cell(store, p)
    await cell(store, kid)
    await cell(store, other)
    mine = await store.made(ops.plane_run(p, into=MADE))
    below = await store.made(ops.plane_run(kid, into=MADE))
    theirs = await store.made(ops.plane_run(other, into=MADE))
    await store.run(ops.remove_plane(p))
    asked = {r["id"]: r["termination_requested"] for r in await store.read(ops.runs())}
    assert asked == {mine: True, below: True, theirs: False}


# --- Cells ---------------------------------------------------------------------


async def test_add_cell_places_by_index(store):
    p = await plane(store)
    a = await cell(store, p, name="a")
    b = await cell(store, p, name="b")
    c = await cell(store, p, name="c", index=0, meta={"k": 1})
    assert c.startswith("c_")
    assert await store.read(ops.cells(p)) == [c, a, b]
    assert await store.read(ops.cell_exists(a)) is True
    assert (await store.read(ops.cell_rows(p)))[0] == {
        "id": c,
        "name": "c",
        "prog": "def out(): pass",
        "props": {"made_by": "", "has_ui": False},
        "meta": {"k": 1},
    }


DRAWS = """\
import nustd.ui


def out(cell):
    return nustd.ui.StatRef(cell).set_label("n")
"""

PLAIN = "import nu\n\n\ndef out():\n    return nu.Noop()\n"


async def has_ui(store, p, c):
    return (await store.read(ops.cell_rows(p)))[0]["props"]["has_ui"]


async def test_add_cell_has_ui_when_its_tree_holds_a_ui_ref(store):
    p = await plane(store)
    c = await cell(store, p, DRAWS)
    assert await has_ui(store, p, c) is True


async def test_add_cell_has_no_ui_when_plain_or_broken(store):
    p = await plane(store)
    c = await cell(store, p, PLAIN)
    assert await has_ui(store, p, c) is False
    await store.run(ops.set_prog(c, "def out("))
    assert await has_ui(store, p, c) is False


async def test_set_prog_recomputes_has_ui(store):
    p = await plane(store)
    c = await cell(store, p, PLAIN)
    await store.run(ops.set_prog(c, DRAWS))
    assert await has_ui(store, p, c) is True
    await store.run(ops.set_prog(c, PLAIN))
    assert await has_ui(store, p, c) is False
    await store.run(ops.add_cell(p, DRAWS, cell_id=c))
    assert await has_ui(store, p, c) is True


async def test_has_ui_reads_true_where_never_worked_out(store):
    p = await plane(store)
    c = await cell(store, p, PLAIN)
    props = Space.cells[c].props
    await store.run(nustd.kv.Transaction(props.del_item("has_ui"), scope=Space))
    assert await has_ui(store, p, c) is True


async def test_add_cell_refuses_a_missing_plane(store):
    assert await store.made(ops.add_cell("nope", "src", into=MADE)) == ""
    assert await store.read(ops.planes()) == []


async def test_add_cell_given_id(store):
    p = await plane(store)
    assert await cell(store, p, cell_id="x") == "x"
    assert await cell(store, p, cell_id="x", name="again") == "x"
    assert await store.read(ops.cells(p)) == ["x"]


async def test_add_cell_points_the_cell_back_at_its_plane(store):
    p = await plane(store)
    a = await cell(store, p)
    assert await store.read(ops.cell_plane(a)) == p
    assert await store.read(Space.planes[p].cells.extract()) == [a]
    assert await store.read(ops.cell_plane("nope")) == ""


async def test_add_cell_refuses_an_id_on_another_plane(store):
    p, q = await plane(store), await plane(store)
    await cell(store, p, cell_id="x", name="first")
    assert await cell(store, q, cell_id="x", name="second") == ""
    assert await store.read(ops.cells(q)) == []
    assert await store.read(ops.cell_plane("x")) == p
    assert (await store.read(ops.cell_rows(p)))[0]["name"] == "first"


async def test_remove_cell(store):
    p = await plane(store)
    a, b = await cell(store, p), await cell(store, p)
    r = await store.made(ops.plane_run(p, into=MADE))
    await store.run(ops.remove_cell(a) >> ops.remove_cell("nope"))
    assert await store.read(ops.cells(p)) == [b]
    assert await store.read(ops.cell_exists(a)) is False
    asked = {c["cell"]: c["interrupt_requested"] for c in await store.read(ops.cell_runs(r))}
    assert asked == {a: True, b: False}


async def test_rename_cell_and_set_prog(store):
    p = await plane(store)
    a = await cell(store, p, name="a")
    await store.run(ops.rename_cell(a, "b") >> ops.set_prog(a, "new"))
    await store.run(ops.set_prog("nope", "x"))
    assert await store.read(ops.prog(a)) == "new"
    assert await store.read(ops.prog("nope")) == ""
    assert await store.read(ops.cells(p)) == [a]
    assert (await store.read(ops.cell_rows(p)))[0]["name"] == "b"


async def test_set_cell_meta_merges(store):
    p = await plane(store)
    a = await cell(store, p, meta={"x": 1})
    await store.run(ops.set_cell_meta(a, {"y": 2}))
    assert (await store.read(ops.cell_rows(p)))[0]["meta"] == {"x": 1, "y": 2}


async def test_reorder_cells(store):
    p = await plane(store)
    a, b, c = [await cell(store, p) for _ in range(3)]
    await store.run(ops.reorder_cells(p, [c, "ghost", a]))
    assert await store.read(ops.cells(p)) == [c, a, b]
    await store.run(ops.reorder_cells(p, nu.List.of(b)))
    assert await store.read(ops.cells(p)) == [b, c, a]


async def version(store, plane_id):
    return await store.read(Space.planes[plane_id].version.fallback(0))


async def test_every_cell_write_counts_on_its_plane(store):
    p, q = await plane(store), await plane(store)
    a = await cell(store, p)
    b = await cell(store, p)
    assert await version(store, p) == 2
    writes = [
        ops.set_prog(a, "x"),
        ops.rename_cell(a, "n"),
        ops.set_cell_meta(a, {"k": 1}),
        ops.reorder_cells(p, [b, a]),
        ops.add_cell(p, "y", cell_id=a),
        ops.remove_cell(b),
    ]
    for n, write in enumerate(writes, start=3):
        await store.run(write)
        assert await version(store, p) == n
    # Nothing on another plane, and nothing for what was not written.
    assert await version(store, q) == 0
    await store.run(ops.rename_cell("nope", "n") >> ops.add_cell(q, "z", cell_id=a))
    assert (await version(store, p), await version(store, q)) == (8, 0)


# --- Nesting -------------------------------------------------------------------


async def test_move_plane_reparents_and_reorders(store):
    a, b, c = await plane(store), await plane(store), await plane(store)
    await store.run(ops.move_plane(b, parent=a) >> ops.move_plane(c, parent=a, index=0))
    assert await store.read(ops.children()) == [a]
    assert await store.read(ops.children(a)) == [c, b]
    await store.run(ops.move_plane(b))
    assert await store.read(ops.children()) == [a, b]
    assert await store.read(ops.children(a)) == [c]
    assert await store.read(ops.parent(c)) == a
    # Within one parent: the index is taken with the plane out of the list.
    await store.run(ops.move_plane(b, parent="", index=0))
    assert await store.read(ops.children()) == [b, a]


async def test_move_plane_refuses_cycles(store):
    a = await plane(store)
    b = await store.made(ops.add_plane(parent=a, backend="async", into=MADE))
    c = await store.made(ops.add_plane(parent=b, backend="async", into=MADE))
    for to in (c, b, a, "nope"):
        await store.run(ops.move_plane(a, parent=to))
        assert await store.read(ops.parent(a)) == ""
    await store.run(ops.move_plane("nope"))
    assert await store.read(ops.parent("nope")) == ""
    assert await store.read(ops.children()) == [a]
    assert await store.read(ops.children(b)) == [c]
    await store.run(ops.move_plane(c, parent=a))
    assert await store.read(ops.parent(c)) == a
    assert await store.read(ops.children(a)) == [b, c]


async def test_move_plane_moves_system_planes_too(store):
    svc = await plane(store, system=True)
    top = await plane(store)
    await store.run(ops.move_plane(svc, parent=top))
    assert await store.read(ops.children(top)) == [svc]


async def test_sibling_order_after_add_remove_and_move(store):
    a, b, c = await plane(store, "a"), await plane(store, "b"), await plane(store, "c")
    # New planes append.
    assert await store.read(ops.children()) == [a, b, c]
    d = await plane(store, "d")
    assert await store.read(ops.children()) == [a, b, c, d]
    # A move places, a removal closes the gap, and the rest keep their order.
    await store.run(ops.move_plane(d, index=1))
    assert await store.read(ops.children()) == [a, d, b, c]
    await store.run(ops.remove_plane(b))
    assert await store.read(ops.children()) == [a, d, c]
    kid = await store.made(ops.add_plane(name="kid", parent=d, backend="async", into=MADE))
    await store.run(ops.move_plane(c, parent=d, index=0))
    assert await store.read(ops.children(d)) == [c, kid]
    assert await store.read(ops.children()) == [a, d]


async def nested(store) -> None:
    """Nesting agrees both ways: each plane is listed once, by the parent it names."""
    rows = await store.read(ops.plane_rows())
    listed = await store.read(ops.children())
    assert sorted(listed) == sorted(r["id"] for r in rows if r["parent"] == "")
    for row in rows:
        assert row["id"] in await store.read(ops.children(row["parent"]))
        kids = await store.read(ops.children(row["id"]))
        assert [await store.read(ops.parent(k)) for k in kids] == [row["id"]] * len(kids)
        listed += kids
    assert sorted(listed) == sorted(r["id"] for r in rows)


async def test_nesting_is_written_both_ways(store):
    a, b = await plane(store, "a"), await plane(store, "b")
    kid = await store.made(ops.add_plane(name="kid", parent=a, backend="async", into=MADE))
    await nested(store)
    # Given again with another parent, it moves: out of the old list, into the new.
    await store.run(ops.add_plane(kid, name="kid", parent=b, backend="async"))
    assert (await store.read(ops.children(a)), await store.read(ops.children(b))) == ([], [kid])
    await nested(store)
    await store.run(ops.move_plane(kid) >> ops.move_plane(a, parent=b, index=0))
    assert await store.read(ops.children()) == [b, kid]
    assert await store.read(ops.children(b)) == [a]
    assert await store.read(ops.parent(kid)) == ""
    await nested(store)


async def test_remove_plane_with_children_leaves_no_listing(store):
    top, keep = await plane(store, "top"), await plane(store, "keep")
    mid = await store.made(ops.add_plane(parent=top, backend="async", into=MADE))
    leaf = await store.made(ops.add_plane(parent=mid, backend="async", into=MADE))
    side = await store.made(ops.add_plane(parent=top, backend="async", into=MADE))
    await store.run(ops.remove_plane(mid))
    assert await store.read(ops.children(top)) == [side]
    assert await store.read(nu.List.of(ops.parent(mid), ops.parent(leaf))) == ["", ""]
    assert await store.read(ops.planes()) == [top, keep, side]
    await nested(store)
    await store.run(ops.remove_plane(top))
    assert await store.read(ops.children()) == [keep]
    await nested(store)


async def test_move_plane_under_a_deep_plane(store):
    a = await plane(store, "a")
    deep = a
    for _ in range(4):
        deep = await store.made(ops.add_plane(parent=deep, backend="async", into=MADE))
    other = await plane(store, "other")
    await store.run(ops.move_plane(other, parent=deep))
    assert await store.read(ops.parent(other)) == deep
    # The top of that chain cannot go under its own bottom.
    await store.run(ops.move_plane(a, parent=other))
    assert await store.read(ops.parent(a)) == ""
    await nested(store)


# --- Pins ----------------------------------------------------------------------


async def test_pin_places_and_moves(store):
    assert await store.read(ops.pinned()) == []
    a, b, c = [await plane(store, ui=True) for _ in range(3)]
    await store.run(ops.pin_plane(a) >> ops.pin_plane(b) >> ops.pin_plane(c, index=0))
    assert await store.read(ops.pinned()) == [c, a, b]
    # Pinned again with no index: stays. With one: moves, the plane taken out first.
    await store.run(ops.pin_plane(c))
    assert await store.read(ops.pinned()) == [c, a, b]
    await store.run(ops.pin_plane(c, index=1))
    assert await store.read(ops.pinned()) == [a, c, b]
    # Out of range, negative included, is the end.
    await store.run(ops.pin_plane(a, index=-1))
    assert await store.read(ops.pinned()) == [c, b, a]
    # A pin is a shortcut: the nesting is untouched.
    assert await store.read(ops.children()) == [a, b, c]


async def test_pin_refuses_missing_and_undrawn_planes(store):
    hidden = await plane(store)
    await store.run(ops.pin_plane("nope") >> ops.pin_plane(hidden, index=0))
    assert await store.read(ops.pinned()) == []


async def test_unpin_and_move_pin(store):
    a, b, c = [await plane(store, ui=True) for _ in range(3)]
    await store.run(ops.pin_plane(a) >> ops.pin_plane(b) >> ops.pin_plane(c))
    await store.run(ops.move_pin(c, 0) >> ops.move_pin(a, 9))
    assert await store.read(ops.pinned()) == [c, b, a]
    await store.run(ops.unpin_plane(b) >> ops.unpin_plane("nope"))
    assert await store.read(ops.pinned()) == [c, a]
    # Moving a plane that is not pinned pins nothing.
    await store.run(ops.move_pin(b, 0))
    assert await store.read(ops.pinned()) == [c, a]
    assert await store.read(ops.planes()) == [a, b, c]


async def test_remove_plane_unpins_its_subtree(store):
    top, keep = await plane(store, ui=True), await plane(store, ui=True)
    kid = await store.made(ops.add_plane(parent=top, ui=True, backend="async", into=MADE))
    await store.run(ops.pin_plane(kid) >> ops.pin_plane(keep) >> ops.pin_plane(top))
    await store.run(ops.remove_plane(top))
    assert await store.read(ops.pinned()) == [keep]


async def test_parent_of_an_unlinked_plane(store):
    assert await store.read(ops.parent("nope")) == ""


async def test_structure_round_trips_through_sqlite(disk):
    """The codec path: nested meta, a cell's props and nested state, order, nesting."""
    p, q, c = "p", "q", "c"
    await disk.run(ops.add_plane(p, name="p", meta={"a": {"b": 1}}, backend="async"))
    await disk.run(ops.add_plane(q, name="q", parent=p, backend="async"))
    await disk.run(ops.add_cell(q, "src", cell_id=c, made_by="m", meta={"m": [1, 2]}))
    cells = States.cells
    await disk.run(nustd.kv.Transaction(cells.set_item(c, {"n": {"deep": [3]}}), scope=States))
    assert await disk.read(ops.plane_rows()) == [
        {"id": p, "name": "p", "props": NO_PROPS, "meta": {"a": {"b": 1}}, "parent": ""},
        {"id": q, "name": "q", "props": NO_PROPS, "meta": {}, "parent": p},
    ]
    assert await disk.read(ops.cell_rows(q)) == [
        {
            "id": c,
            "name": "",
            "prog": "src",
            "props": {"made_by": "m", "has_ui": False},
            "meta": {"m": [1, 2]},
        }
    ]
    assert await disk.read(States.cells[c].extract()) == {"n": {"deep": [3]}}
    await disk.run(ops.remove_plane(p))
    assert await disk.read(ops.planes()) == []
    assert await disk.read(nu.list(States.planes.keys())) == []
    assert await disk.read(nu.list(States.cells.keys())) == []
