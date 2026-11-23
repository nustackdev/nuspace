"""``nuspace.web.layout``: the layout model and its fix-up, the layout ops, transfer and place, and the pane.

Every op is a bare term, run here inside ``nuspace.atomic`` as a caller
would (``transfer_cell`` brackets itself). The pane runs in one tab over a
fake session, as ``test_web.py``.
"""

from __future__ import annotations

import asyncio

import pytest

import nu
import nuspace
import nuspace.web as web
from nuspace.errors import Exists, Missing, Refused, Removed
from nuspace.shapes import Space
from nuspace.specs import space_registry
from nuspace.web.items import ITEM_ID
from nuspace.web.layout.model import (
    cells_problem,
    column_problem,
    fills,
    item_problem,
    layout_view,
    plan,
    put_in,
    taken_out,
    write_problem,
)
from nuspace.web.shapes import Web
from nustd.ui.core import OP_NOTIFY, Frame, WsSession
from nustd.ui.core.session import Session


#: Run on both backends: in memory, and the space's sqlite files.
STORES = ("memory", "sqlite")

L = web.layout


def cell(c: str) -> dict:
    return {"kind": "cell", "cell": c}


def strip(*columns: list[str], shares: list[float] | None = None) -> dict:
    """A strip of ``columns``, each a list of cells, at ``shares`` (even when left out)."""
    held = shares or [1 / len(columns)] * len(columns)
    return {
        "kind": "strip",
        "columns": [{"cells": list(c), "share": s} for c, s in zip(columns, held, strict=True)],
    }


def shown(view: list[dict]) -> list:
    """A read as ``[cell]`` per cell item and ``[[cells], ...]`` per strip: what the eye sees."""
    return [i["cell"] if i["kind"] == "cell" else [c["cells"] for c in i["columns"]] for i in view]


async def do(store, term):
    return await store.run(nuspace.atomic(term))


async def plane(store, pid: str, *cells: str) -> None:
    """A web plane with ``cells``, in that order."""
    await do(store, nuspace.plane.add(pid, backend="async"))
    await do(store, web.add(pid, editable=True))
    for c in cells:
        await do(store, nuspace.cell.add(pid, "x = 1", id=c, fabrics=[]))


async def read(store, pid: str = "p1") -> list[dict]:
    return await store.read(L.get_layout(pid))


async def stored(store, pid: str = "p1") -> dict:
    layout = Web.planes[pid].layout
    return await store.read(nu.If(layout.exists(), layout.extract(), nu.Literal({})))


def ids_of(view: list[dict]) -> list[str]:
    return [i["id"] for i in view]


# --- The model: shape --------------------------------------------------------------------


def test_a_cell_item_and_a_strip_are_items():
    assert item_problem(cell("c1")) == ""
    assert item_problem(strip(["c1", "c2"], ["c3"], shares=[0.7, 0.3])) == ""
    assert item_problem(strip(["c1", "c2"])) == ""


@pytest.mark.parametrize(
    ("held", "said"),
    [
        ("nope", "item is not a dict"),
        ({"kind": "plane", "cell": "c1"}, "item kind is not"),
        ({"kind": "cell"}, "item has keys"),
        ({"kind": "cell", "cell": "c1", "id": "abcdef"}, "item has keys"),
        ({"kind": "cell", "cell": ""}, "item cell is not a cell id"),
        ({"kind": "strip", "columns": []}, "strip has no columns"),
        (strip(["c1"], ["c2"], shares=[0.5, 0.4]), "strip shares do not sum to 1"),
        (strip(["c1"], ["c2"], shares=[0, 1]), "strip column 0 share is not a number"),
        (strip([], ["c2", "c3"]), "strip column 0 cells is not a list of cell ids"),
        (strip(["c1"]), "strip has one cell, a cell item then"),
        (strip(["c1", "c2"], ["c1"]), "strip holds cell c1 twice"),
        ({"kind": "strip", "columns": [{"cells": ["c1", "c2"]}]}, "strip column 0 has keys"),
    ],
)
def test_an_item_off_the_shape_says_why(held, said):
    assert item_problem(held).startswith(said)


def test_a_write_is_checked_whole():
    good = {"sets": {"abcdef": cell("c1")}, "deletes": ["zzzzzz"], "order": None}
    assert write_problem(good) == ""
    assert write_problem({**good, "order": ["abcdef"]}) == ""
    assert write_problem({**good, "sets": {"BAD": cell("c1")}}).startswith("item id 'BAD'")
    assert write_problem({**good, "sets": {"abcdef": {"kind": "x"}}}).endswith("(item abcdef)")
    assert write_problem({**good, "deletes": "x"}) == "write deletes is not a list of ids"
    assert write_problem({**good, "order": [1]}) == "write order is not a list of ids"
    assert write_problem({"sets": {}}).startswith("write has keys")


def test_cells_must_be_on_the_plane_and_in_one_item():
    entries = {"aaaaaa": cell("c1"), "bbbbbb": strip(["c2"], ["c3"])}
    on = ["c1", "c2", "c3", "c4"]
    assert cells_problem(entries, on, {"cccccc": cell("c4")}, []) == ""
    assert cells_problem(entries, on, {"cccccc": cell("c9")}, []) == "cell c9 is not on the plane"
    assert cells_problem(entries, on, {"cccccc": cell("c2")}, []) == (
        "cell c2 is in items bbbbbb and cccccc"
    )
    # Moved between items in one write: out of one, into the other.
    moved = {"aaaaaa": strip(["c1", "c2"]), "bbbbbb": cell("c3")}
    assert cells_problem(entries, on, moved, []) == ""
    # Deleted in the same write frees its cells.
    assert cells_problem(entries, on, {"cccccc": strip(["c2", "c3"])}, ["bbbbbb"]) == ""
    # Two stored items holding one cell, neither written: not this write's.
    twice = {**entries, "dddddd": cell("c1")}
    assert cells_problem(twice, on, {"cccccc": cell("c4")}, []) == ""


def test_a_column_is_one_of_a_strips():
    held = strip(["c1"], ["c2"])
    assert column_problem(held, 1) == ""
    assert column_problem(held, 2) == "column 2 is not one of the strip's 2"
    assert column_problem(held, True).startswith("column True")
    assert column_problem(cell("c1"), 0) == "item is not a strip"
    assert put_in(held, "c9", 1, 0)["columns"][1]["cells"] == ["c9", "c2"]
    assert put_in(held, "c9", 0, 99)["columns"][0]["cells"] == ["c1", "c9"]


# --- The model: the fix-up ---------------------------------------------------------------


def test_an_empty_layout_reads_as_one_cell_item_per_cell_in_order():
    view = layout_view({}, ["c1", "c2", "c3"])
    assert shown(view) == ["c1", "c2", "c3"]
    assert all(ITEM_ID.fullmatch(i) for i in ids_of(view))
    # The same state reads the same ids, so the browser can anchor on them.
    assert ids_of(layout_view(None, ["c1", "c2", "c3"])) == ids_of(view)
    assert layout_view({}, []) == []


def test_a_cell_no_longer_on_the_plane_is_skipped_and_its_item_stays():
    entries = {"aaaaaa": cell("c1"), "bbbbbb": cell("c2"), "cccccc": cell("c3")}
    # c2 removed or transferred out: skipped, nothing drawn in its place.
    view = layout_view(entries, ["c1", "c3"])
    assert [(i["id"], i["cell"]) for i in view] == [("aaaaaa", "c1"), ("cccccc", "c3")]
    # Back on the plane, it reads where it was, whatever its place in cells.
    view = layout_view(entries, ["c2", "c1", "c3"])
    assert ids_of(view) == ["aaaaaa", "bbbbbb", "cccccc"]


def test_the_strip_rules_after_skipping():
    held = strip(["c1", "c2"], ["c3"], ["c4"], shares=[0.5, 0.25, 0.25])
    # An empty column goes, the shares left rescale.
    (one,) = layout_view({"aaaaaa": held}, ["c1", "c2", "c4"])
    assert one["id"] == "aaaaaa"
    assert [c["cells"] for c in one["columns"]] == [["c1", "c2"], ["c4"]]
    assert [c["share"] for c in one["columns"]] == pytest.approx([2 / 3, 1 / 3])
    # A cell out of a column that stays: the shares stay.
    (one,) = layout_view({"aaaaaa": held}, ["c1", "c3", "c4"])
    assert [c["share"] for c in one["columns"]] == [0.5, 0.25, 0.25]
    # One cell left: a cell item, same id.
    assert layout_view({"aaaaaa": held}, ["c3"]) == [{"id": "aaaaaa", "kind": "cell", "cell": "c3"}]
    # None left: gone.
    assert layout_view({"aaaaaa": held}, ["c9"]) == [layout_view({}, ["c9"])[0]]


def test_a_new_cell_goes_after_its_predecessors_item():
    entries = {"aaaaaa": cell("c3"), "bbbbbb": cell("c1")}
    # c2 is after c1 in cells: right after c1's item, wherever that is.
    assert shown(layout_view(entries, ["c1", "c2", "c3"])) == ["c3", "c1", "c2"]
    # c0 is first in cells: the top.
    assert shown(layout_view(entries, ["c0", "c1", "c3"])) == ["c0", "c3", "c1"]
    # Two new in a row chain after each other.
    assert shown(layout_view(entries, ["c3", "n1", "n2", "c1"])) == ["c3", "n1", "n2", "c1"]


def test_a_new_cell_after_a_cell_inside_a_strip_goes_after_the_strip():
    entries = {"aaaaaa": strip(["c1"], ["c3"]), "bbbbbb": cell("c4")}
    view = layout_view(entries, ["c1", "c2", "c3", "n1", "c4"])
    # c2 follows c1, n1 follows c3: both after the strip, in cells order.
    assert shown(view) == [[["c1"], ["c3"]], "c2", "n1", "c4"]


def test_a_cell_two_stored_items_hold_shows_in_the_first():
    entries = {"aaaaaa": cell("c1"), "bbbbbb": strip(["c1", "c2"], ["c3"])}
    assert shown(layout_view(entries, ["c1", "c2", "c3"])) == ["c1", [["c2"], ["c3"]]]


def test_an_entry_off_the_shape_is_skipped_and_its_cell_filled():
    entries = {"aaaaaa": {"kind": "pane"}, "bbbbbb": cell("c2")}
    assert shown(layout_view(entries, ["c1", "c2"])) == ["c1", "c2"]


def test_a_fill_id_never_takes_a_stored_one():
    (first,) = layout_view({}, ["c1"])
    # Store something under the id c1 would get: c1 reads under another.
    (_, again) = layout_view({first["id"]: cell("c0")}, ["c0", "c1"])
    assert again["cell"] == "c1" and again["id"] != first["id"]


def test_fills_are_the_reads_additions_as_inserts():
    entries = {"aaaaaa": cell("c2"), "bbbbbb": cell("gone")}
    view = layout_view(entries, ["c0", "c1", "c2", "c3"])
    got = fills(entries, ["c0", "c1", "c2", "c3"])
    c0, c1, _, c3 = ids_of(view)
    assert got == [
        [c0, cell("c0"), "before", "aaaaaa"],
        [c1, cell("c1"), "after", c0],
        [c3, cell("c3"), "after", "aaaaaa"],
    ]
    # Applied in order the store reads back as the read did: the hidden item kept.
    order = list(entries)
    for item_id, _, side, anchor in got:
        order.insert(order.index(anchor) + (side == "after"), item_id)
    assert order == [c0, c1, "aaaaaa", c3, "bbbbbb"]
    assert fills({}, ["c1"]) == [[ids_of(layout_view({}, ["c1"]))[0], cell("c1"), "end", ""]]
    assert fills(entries, ["c2"]) == []


def test_taken_out_follows_the_strip_rules():
    entries = {
        "aaaaaa": cell("c1"),
        "bbbbbb": strip(["c1", "c2"], ["c3"]),
        "cccccc": strip(["c4"], ["c1"], shares=[0.25, 0.75]),
        "dddddd": cell("c5"),
    }
    got = taken_out(entries, ["c1"])
    assert got["deletes"] == ["aaaaaa"]
    assert got["sets"] == {"bbbbbb": strip(["c2"], ["c3"]), "cccccc": cell("c4")}
    assert taken_out(entries, ["c9"]) == {"sets": {}, "deletes": []}
    # Item ``but`` keeps its cells; several cells at once.
    assert taken_out(entries, ["c1"], "aaaaaa")["deletes"] == []
    assert taken_out(entries, ["c1", "c4"])["deletes"] == ["aaaaaa", "cccccc"]


# --- The ops -----------------------------------------------------------------------------


async def test_a_new_plane_reads_its_cells_in_order_and_stores_nothing(store):
    await plane(store, "p1", "c1", "c2")
    assert shown(await read(store)) == ["c1", "c2"]
    assert await stored(store) == {}


async def test_every_op_fills_first_with_the_reads_ids(store):
    await plane(store, "p1", "c1", "c2", "c3")
    before = await read(store)
    c1, c2, c3 = ids_of(before)
    # Anchored on items only the read had: they are stored first, then moved.
    await do(store, L.move_item("p1", c3, before=c1))
    assert ids_of(await read(store)) == [c3, c1, c2]
    assert list(await stored(store)) == [c3, c1, c2]


async def test_add_set_remove_and_move_items(store):
    await plane(store, "p1", "c1", "c2", "c3")
    c1, c2, c3 = ids_of(await read(store))
    # A strip made of c1 and c2 in one write: the two cell items out, the strip in.
    await do(store, L.write_items("p1", {"stripa": strip(["c1"], ["c2"])}, [c1, c2], ["stripa"]))
    assert shown(await read(store)) == [[["c1"], ["c2"]], "c3"]
    # Resize the strip's columns.
    await do(store, L.set_item("p1", "stripa", strip(["c1"], ["c2"], shares=[0.7, 0.3])))
    assert (await read(store))[0]["columns"][0]["share"] == 0.7
    # Move the cell item first, then last.
    await do(store, L.move_item("p1", c3, before="stripa"))
    assert ids_of(await read(store)) == [c3, "stripa"]
    await do(store, L.move_item("p1", c3))
    assert ids_of(await read(store)) == ["stripa", c3]
    # Remove the strip: its cells still on the plane read on their own.
    await do(store, L.remove_item("p1", "stripa"))
    assert shown(await read(store)) == ["c1", "c2", "c3"]
    # Add: placed, then its cells out of every other item, so the anchor may empty.
    c1, c2, c3 = ids_of(await read(store))
    await do(store, L.add_item("p1", strip(["c3"], ["c1"]), id="stripb", before=c1))
    assert ids_of(await read(store)) == ["stripb", c2]
    assert shown(await read(store)) == [[["c3"], ["c1"]], "c2"]
    # Set: a cell dropped beside another makes a strip in one op, out of where it was.
    await do(store, L.set_item("p1", c2, strip(["c2", "c1"])))
    assert shown(await read(store)) == ["c3", [["c2", "c1"]]]
    # An id left out is minted.
    await do(store, L.add_item("p1", cell("c1")))
    added = (await read(store))[-1]
    assert added["cell"] == "c1" and ITEM_ID.fullmatch(added["id"])


async def test_a_removed_cell_is_skipped_and_its_item_stays(store):
    await plane(store, "p1", "c1", "c2", "c3")
    c1, _, c3 = ids_of(await read(store))
    await do(store, L.move_item("p1", c1))
    assert shown(await read(store)) == ["c2", "c3", "c1"]
    await do(store, nuspace.cell.remove("c3"))
    assert shown(await read(store)) == ["c2", "c1"]
    assert (await stored(store))[c3] == cell("c3")
    # Nothing can place it: it is not on the plane.
    with pytest.raises(Refused, match="cell c3 is not on the plane"):
        await do(store, L.set_item("p1", c3, cell("c3")))


async def test_write_items_orders_and_skips_missing_deletes(store):
    await plane(store, "p1", "c1", "c2", "c3")
    c1, c2, c3 = ids_of(await read(store))
    await do(store, L.write_items("p1", {}, ["zzzzzz"], [c3, c1]))
    assert ids_of(await read(store)) == [c3, c1, c2]


async def test_item_ops_refuse_what_they_cannot_do(store):
    await plane(store, "p1", "c1", "c2")
    await plane(store, "p2", "d1")
    await do(store, nuspace.plane.add("bare", backend="async"))
    c1, c2 = ids_of(await read(store))
    refusals = [
        (L.add_item("nope", cell("c1")), Missing, "no plane nope"),
        (L.add_item("bare", cell("c1")), Missing, "not on the web"),
        (L.add_item("p1", cell("c1"), id="BAD"), Refused, "item id 'BAD'"),
        (L.add_item("p1", {"kind": "x"}), Refused, "item kind"),
        (L.add_item("p1", cell("c1"), id=c2), Exists, f"item {c2} exists"),
        (L.add_item("p1", cell("d1")), Refused, "cell d1 is not on the plane"),
        (L.add_item("p1", cell("c9"), before="zzzzzz"), Refused, "not on the plane"),
        (L.set_item("p1", "zzzzzz", cell("c1")), Missing, "no item zzzzzz"),
        (L.set_item("p1", c1, strip(["c1"], ["d1"])), Refused, "cell d1 is not on the plane"),
        (L.set_item("p1", c1, strip(["c1"])), Refused, "strip has one cell"),
        (L.remove_item("p1", "zzzzzz"), Missing, "no item zzzzzz"),
        (L.move_item("p1", "zzzzzz"), Missing, "no item zzzzzz"),
        (L.move_item("p1", c1, before="zzzzzz"), Missing, "no item zzzzzz"),
        (L.move_item("p1", c1, after=c1), Refused, "cannot move next to itself"),
        (L.write_items("p1", {"BAD": cell("c1")}), Refused, "item id 'BAD'"),
        (L.write_items("p1", {"newone": cell("c1")}), Refused, "cell c1 is in items"),
    ]
    for term, exc, said in refusals:
        with pytest.raises(exc, match=said):
            await do(store, term)
    with pytest.raises(TypeError):
        L.move_item("p1", c1, before=c2, after=c2)
    # Nothing was written: refused ops roll their fill back with them, and no web row was made.
    assert await stored(store) == {}
    assert not await store.read(Web.planes.contains("bare"))
    await do(store, nuspace.plane.remove("p1"))
    with pytest.raises(Removed):
        await do(store, L.move_item("p1", c1))


# --- Placing one cell, and transfer then place -------------------------------------------


async def test_place_cell_takes_it_out_and_puts_it_at_a_spot(store):
    await plane(store, "p1", "c1", "c2", "c3", "c4")
    c1, c2, _, c4 = ids_of(await read(store))
    await do(store, L.write_items("p1", {"stripa": strip(["c1"], ["c2"])}, [c1, c2], ["stripa"]))
    assert shown(await read(store)) == [[["c1"], ["c2"]], "c3", "c4"]
    # Into a column: out of its own item, stacked under c1.
    await do(store, L.place_cell("p1", "c3", into="stripa", column=0, index=1))
    assert shown(await read(store)) == [[["c1", "c3"], ["c2"]], "c4"]
    # Out of the strip to its own item before c4: the strip rules on what it left.
    await do(store, L.place_cell("p1", "c2", before=c4, id="ownone"))
    assert shown(await read(store)) == [[["c1", "c3"]], "c2", "c4"]
    assert (await read(store))[0]["columns"][0]["share"] == 1
    # No spot: last.
    await do(store, L.place_cell("p1", "c1"))
    assert shown(await read(store)) == ["c3", "c2", "c4", "c1"]
    # Anchored on the item it leaves: placed first, then out of it.
    await do(store, L.place_cell("p1", "c4", after="ownone"))
    assert shown(await read(store)) == ["c3", "c2", "c4", "c1"]
    c4_item = (await read(store))[2]["id"]
    await do(store, L.place_cell("p1", "c4", before=c4_item, id="again1"))
    assert ids_of(await read(store))[2] == "again1"


async def test_place_cell_refuses_what_it_cannot_do(store):
    await plane(store, "p1", "c1", "c2", "c3")
    await plane(store, "p2", "d1")
    c1, _, _ = ids_of(await read(store))
    refusals = [
        (L.place_cell("p1", "d1"), Refused, "cell d1 is not on plane p1"),
        (L.place_cell("p1", "c2", into="zzzzzz", column=0, index=0), Missing, "no item"),
        (L.place_cell("p1", "c2", into=c1, column=0, index=0), Refused, "is not a strip"),
        (L.place_cell("p1", "c2", before="zzzzzz"), Missing, "no item zzzzzz"),
    ]
    for term, exc, said in refusals:
        with pytest.raises(exc, match=said):
            await do(store, term)
    await do(store, L.set_item("p1", c1, strip(["c1"], ["c3"])))
    with pytest.raises(Refused, match="column 2 is not one"):
        await do(store, L.place_cell("p1", "c2", into=c1, column=2, index=0))
    with pytest.raises(TypeError):
        L.place_cell("p1", "c2", into=c1, column=0, index=0, before=c1)
    with pytest.raises(TypeError):
        L.place_cell("p1", "c2", into=c1)


async def test_transfer_cell_transfers_then_places_in_two_commits(store):
    await plane(store, "p1", "c1", "c2")
    await plane(store, "p2", "d1", "d2", "d3")
    d1, d2, d3 = ids_of(await read(store, "p2"))
    await do(store, L.write_items("p2", {"stripb": strip(["d1"], ["d2"])}, [d1, d2], ["stripb"]))
    await store.run(L.transfer_cell("c1", "p2", into="stripb", column=1, index=0))
    assert await store.read(Space.cells["c1"].plane) == "p2"
    assert shown(await read(store, "p2")) == [[["d1"], ["c1", "d2"]], "d3"]
    assert shown(await read(store, "p1")) == ["c2"]
    await store.run(L.transfer_cell("c2", "p2", before=d3))
    assert shown(await read(store, "p2")) == [[["d1"], ["c1", "d2"]], "c2", "d3"]
    # The old plane's item stays: transferred back, the cell reads where it was.
    await do(store, L.move_item("p2", d3, before="stripb"))
    p1_kept = await stored(store, "p1")
    assert p1_kept == {}
    # A failed place leaves the cell transferred, drawn last by the fix-up.
    await plane(store, "p3", "e1")
    with pytest.raises(Missing):
        await store.run(L.transfer_cell("c2", "p3", before="zzzzzz"))
    assert await store.read(Space.cells["c2"].plane) == "p3"
    assert shown(await read(store, "p3")) == ["e1", "c2"]
    # A cell on the plane already is only placed.
    await store.run(L.transfer_cell("c2", "p3", before=ids_of(await read(store, "p3"))[0]))
    assert shown(await read(store, "p3")) == ["c2", "e1"]
    # A transfer refused writes nothing, and nothing is placed.
    await do(store, nuspace.plane.add("sys", backend="async", system=True))
    with pytest.raises(Refused):
        await store.run(L.transfer_cell("c2", "sys"))
    assert await store.read(Space.cells["c2"].plane) == "p3"


async def test_a_cell_transferred_back_shows_in_its_old_item(store):
    await plane(store, "p1", "c1", "c2", "c3")
    c1, _, c3 = ids_of(await read(store))
    await do(store, L.write_items("p1", {"stripa": strip(["c1"], ["c3"])}, [c1, c3], ["stripa"]))
    await plane(store, "p2", "d1")
    await store.run(L.transfer_cell("c3", "p2"))
    assert shown(await read(store)) == ["c1", "c2"]
    assert shown(await read(store, "p2")) == ["d1", "c3"]
    # Back with the core op alone: its old strip shows it again.
    await do(store, nuspace.cell.transfer("c3", "p1"))
    assert shown(await read(store)) == [[["c1"], ["c3"]], "c2"]
    # Back placed: out of its old strip, at the spot.
    await store.run(L.transfer_cell("c3", "p2"))
    await store.run(L.transfer_cell("c3", "p1", before="stripa"))
    assert shown(await read(store)) == ["c3", "c1", "c2"]


# --- The pane, one tab -------------------------------------------------------------------


class FakeSession(WsSession):
    """A session with no socket: frames sent are kept, notifies are fired by hand."""

    def __init__(self) -> None:
        super().__init__(ws=None)
        self.frames: list[Frame] = []

    async def send(self, frame: Frame) -> None:
        self.frames.append(frame)

    def notify(self, path: tuple[str, ...], payload: dict) -> None:
        self._dispatch(Frame(OP_NOTIFY, ref=path, payload=payload))

    def pane(self, plane: str, op: str) -> list[dict]:
        at = ("viewer", "panes", plane)
        return [
            f.payload
            for f in self.frames
            if tuple(f.ref) == at and isinstance(f.payload, dict) and f.payload.get("op") == op
        ]

    def toasts(self) -> list[dict]:
        return [f.payload for f in self.frames if f.ref == ("toast",) and f.payload]


#: A tab compiles its whole term before the first frame: slow on a loaded machine.
BOOT_TIMEOUT = 30.0

P1 = ("viewer", "panes", "p1", "ops")
P2 = ("viewer", "panes", "p2", "ops")


async def _until(check, timeout: float = 3.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not check():
        assert asyncio.get_running_loop().time() < deadline, "timed out"
        await asyncio.sleep(0.01)


def _tab(store, sid):
    from nuspace.web.device import connection

    session = FakeSession()
    ctx = store.ctx.bind(Session, session)
    registry = space_registry(extensions=["testing"])
    task = asyncio.create_task(nu.arun(connection(nu.Str(sid), registry=registry), ctx))
    return session, task


async def test_the_pane_ships_its_layout_with_its_cells_and_hears_the_layout_events(store):
    await plane(store, "p1", "c1", "c2", "c3")
    await plane(store, "p2", "d1")
    session, task = _tab(store, "s1")

    def last(plane: str = "p1") -> dict:
        return session.pane(plane, "set_cells")[-1]

    def view(plane: str = "p1") -> list:
        return shown(last(plane)["layout"])

    try:
        await _until(lambda: session.frames, BOOT_TIMEOUT)
        session.notify(("viewer", "ops", "planes.open"), {"plane_ids": ["p1", "p2"], "params": {}})
        await _until(lambda: session.pane("p1", "set_cells") and session.pane("p2", "set_cells"))
        # Cells and layout in one write, read from one snapshot.
        assert [c["id"] for c in last()["cells"]] == ["c1", "c2", "c3"]
        assert view() == ["c1", "c2", "c3"]
        c1, _, c3 = ids_of(last()["layout"])
        heads = len(session.pane("p1", "set_head"))

        # layout.move: the web plane's reorder, the layout only, cells order untouched.
        session.notify((*P1, "layout.move"), {"item_id": c3, "before": c1})
        await _until(lambda: view() == ["c3", "c1", "c2"])
        assert await store.read(nu.list(Space.planes["p1"].cells.keys())) == ["c1", "c2", "c3"]
        # layout.set: a cell dropped beside another makes a strip, out of its own item.
        made = strip(["c1"], ["c2"])
        session.notify((*P1, "layout.set"), {"item_id": c1, "item": made})
        await _until(lambda: view() == ["c3", [["c1"], ["c2"]]])
        # layout.set: a column resized.
        resized = strip(["c1"], ["c2"], shares=[0.6, 0.4])
        session.notify((*P1, "layout.set"), {"item_id": c1, "item": resized})
        await _until(lambda: last()["layout"][1]["columns"][0]["share"] == 0.6)
        # layout.place: a cell into a column.
        session.notify(
            (*P1, "layout.place"), {"cell_id": "c3", "into": c1, "column": 1, "index": 0}
        )
        await _until(lambda: view() == [[["c1"], ["c3", "c2"]]])
        # layout.place: out to its own item, last.
        session.notify((*P1, "layout.place"), {"cell_id": "c3"})
        await _until(lambda: view() == [[["c1"], ["c2"]], "c3"])
        # A cell write reships the layout with the cells: a new cell after its predecessor.
        await do(store, nuspace.cell.add("p1", "x = 1", id="c4", after="c1", fabrics=[]))
        await _until(lambda: view() == [[["c1"], ["c2"]], "c4", "c3"])
        # A removed cell is skipped.
        await do(store, nuspace.cell.remove("c4"))
        await _until(lambda: view() == [[["c1"], ["c2"]], "c3"])

        # layout.transfer: to another pane's plane, at a spot there, and back into a column.
        (d1,) = ids_of(last("p2")["layout"])
        session.notify((*P1, "layout.transfer"), {"cell_id": "c3", "plane_id": "p2", "before": d1})
        await _until(lambda: view("p2") == ["c3", "d1"] and "c3" not in view())
        session.notify(
            (*P2, "layout.transfer"),
            {"cell_id": "c3", "plane_id": "p1", "into": c1, "column": 0, "index": 0},
        )
        await _until(lambda: view() == [[["c3", "c1"], ["c2"]]] and view("p2") == ["d1"])
        assert session.toasts() == []
        # No layout write ever reshipped the head.
        assert len(session.pane("p1", "set_head")) == heads

        # Refusals toast, the arm keeps listening.
        refused = [
            ("layout.move", {"item_id": "zzzzzz"}, "Missing"),
            ("layout.move", {"item_id": c1, "before": "a", "after": "b"}, "ValueError"),
            ("layout.set", {"item_id": c1, "item": strip(["c1"])}, "Refused"),
            ("layout.set", {"item_id": c1}, "ValueError"),
            ("layout.place", {"cell_id": "d1"}, "Refused"),
            ("layout.place", {"cell_id": "c1", "into": c1, "column": -1}, "ValueError"),
            ("layout.place", {"cell_id": "c1", "into": c1}, "ValueError"),
            ("layout.place", {"cell_id": "c1", "into": c1, "before": "x"}, "ValueError"),
            ("layout.transfer", {"cell_id": "c1", "plane_id": "nope"}, "Missing"),
        ]
        for n, (op, payload, kind) in enumerate(refused, start=1):
            session.notify((*P1, op), payload)
            await _until(lambda n=n: len(session.toasts()) == n)
            assert session.toasts()[-1]["type"] == kind, (op, session.toasts()[-1])
        session.notify((*P1, "layout.place"), {"cell_id": "c2"})
        await _until(lambda: view() == [[["c3", "c1"]], "c2"])
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


def test_plan_is_pure_the_same_reads_give_the_same_writes():
    """A plan runs as a query: no random ids, and its inputs are left as they were."""
    plane = {"id": "p", "known": True, "removed": False, "on_web": True}
    entries = {
        "aaaaaa": {
            "kind": "strip",
            "columns": [{"cells": ["a"], "share": 0.5}, {"cells": ["b"], "share": 0.5}],
        }
    }
    cells = ["a", "b", "c"]
    frozen = repr(entries), repr(cells)
    for op, args in (
        ("place", {"cell": "a", "on": "p"}),
        ("add", {"item": {"kind": "cell", "cell": "b"}}),
    ):
        first = plan(op, plane, entries, cells, args)
        assert plan(op, plane, entries, cells, args) == first
    assert (repr(entries), repr(cells)) == frozen
