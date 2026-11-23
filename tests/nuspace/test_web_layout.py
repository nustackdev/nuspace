"""``nuspace.web.layout``: the rows' shape and the reconcile, ``get`` / ``set`` / ``transfer``, and the pane.

The ops are bare terms, run here inside ``nuspace.atomic`` as a caller
would (``transfer`` brackets itself). The pane runs in one tab over a fake
session, as ``test_web.py``.
"""

from __future__ import annotations

import asyncio
import copy

import pytest
from _support.made import MADE

import nu
import nuspace
import nuspace.web as web
from nuspace.errors import Missing, Refused, Removed
from nuspace.shapes import Space
from nuspace.specs import space_registry
from nuspace.web.layout.model import reconcile, rows_problem
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


def shown(rows: list[dict]) -> list:
    """Rows as ``cell`` per cell row and ``[[cells], ...]`` per strip: what the eye sees."""
    return [r["cell"] if r["kind"] == "cell" else [c["cells"] for c in r["columns"]] for r in rows]


async def do(store, term):
    return await store.run(nuspace.atomic(term))


async def plane(store, pid: str, *cells: str) -> None:
    """A web plane with ``cells``."""
    await do(store, nuspace.plane.add(pid, backend="async"))
    await do(store, web.add(pid, editable=True))
    for c in cells:
        await do(store, nuspace.cell.add(pid, "x = 1", id=c, fabrics=[]))


async def get(store, pid: str = "p1") -> list[dict]:
    """The layout through ``get``, in its own commit: it may heal the slot."""
    return await store.made(nuspace.atomic(L.get(pid, into=MADE)))


async def stored(store, pid: str = "p1") -> list | None:
    """The raw slot, None when never written. Only a test reads it."""
    slot = Web.planes[pid].layout
    return await store.read(nu.If(slot.exists(), slot, None))


# --- The model: shape --------------------------------------------------------------------


def test_cell_rows_and_strips_are_a_layout():
    assert rows_problem([]) == ""
    assert rows_problem([cell("c1"), strip(["c2", "c3"], ["c4"], shares=[0.7, 0.3])]) == ""
    # One cell in a strip, or a cell twice, is on the shape: the reconcile's to fix.
    assert rows_problem([strip(["c1"]), cell("c1")]) == ""


@pytest.mark.parametrize(
    ("held", "said"),
    [
        ("nope", "layout is not a list of rows"),
        ([1], "row 0 is not a dict"),
        ([{"kind": "plane", "cell": "c1"}], "row 0 kind is not"),
        ([cell("c1"), {"kind": "cell"}], "row 1 has keys"),
        ([{"kind": "cell", "cell": "c1", "id": "x"}], "row 0 has keys"),
        ([{"kind": "cell", "cell": ""}], "row 0 cell is not a cell id"),
        ([{"kind": "strip", "columns": []}], "row 0 has no columns"),
        ([strip(["c1"], ["c2"], shares=[0.5, 0.4])], "row 0 shares do not sum to 1"),
        ([strip(["c1"], ["c2"], shares=[0, 1])], "row 0 column 0 share is not a number"),
        ([strip([], ["c2", "c3"])], "row 0 column 0 cells is not a list of cell ids"),
        ([{"kind": "strip", "columns": [{"cells": ["c1"]}]}], "row 0 column 0 has keys"),
    ],
)
def test_rows_off_the_shape_say_why(held, said):
    assert rows_problem(held).startswith(said)


# --- The model: the reconcile ------------------------------------------------------------


def test_an_empty_layout_is_every_cell_its_own_row():
    assert reconcile([], ["c1", "c2", "c3"]) == [cell("c1"), cell("c2"), cell("c3")]
    assert reconcile(None, ["c1"]) == [cell("c1")]
    assert reconcile([], []) == []


def test_a_layout_in_step_with_the_cells_reads_back_as_it_is():
    rows = [strip(["c1", "c3"], ["c2"], shares=[0.3, 0.7]), cell("c4")]
    assert reconcile(rows, ["c4", "c3", "c2", "c1"]) == rows


def test_cells_no_longer_on_the_plane_go_by_the_strip_rules():
    rows = [cell("c1"), strip(["c2", "c3"], ["c4"], shares=[0.6, 0.4]), strip(["c5"], ["c6"])]
    # c1 removed: its row goes.
    assert shown(reconcile(rows, ["c2", "c3", "c4", "c5", "c6"])) == [
        [["c2", "c3"], ["c4"]],
        [["c5"], ["c6"]],
    ]
    # c4 out: its column goes, the share left rescales to 1.
    got = reconcile(rows, ["c1", "c2", "c3", "c5", "c6"])
    assert got[1] == strip(["c2", "c3"], shares=[1.0])
    # c2 and c3 out: the strip left with c4 alone is a cell row.
    assert reconcile(rows, ["c1", "c4", "c5", "c6"])[1] == cell("c4")
    # Every cell of a strip out: the strip goes.
    assert shown(reconcile(rows, ["c1", "c5", "c6"])) == ["c1", [["c5"], ["c6"]]]
    # A three column strip losing one: the two left keep their ratio.
    three = [strip(["a"], ["b"], ["c"], shares=[0.2, 0.2, 0.6])]
    shares = [c["share"] for c in reconcile(three, ["a", "c"])[0]["columns"]]
    assert shares == pytest.approx([0.25, 0.75])


def test_a_cell_in_two_places_stays_with_its_first_holder():
    rows = [strip(["c1"], ["c2"]), cell("c1"), strip(["c2", "c3"], ["c4"])]
    assert shown(reconcile(rows, ["c1", "c2", "c3", "c4"])) == [
        [["c1"], ["c2"]],
        [["c3"], ["c4"]],
    ]
    # Twice inside one strip.
    assert reconcile([strip(["c1", "c1"], ["c2"])], ["c1", "c2"]) == [strip(["c1"], ["c2"])]


def test_new_cells_go_last_in_cells_order():
    rows = [strip(["c1"], ["c2"])]
    assert shown(reconcile(rows, ["c3", "c1", "c4", "c2"])) == [[["c1"], ["c2"]], "c3", "c4"]


def test_a_row_off_the_shape_is_dropped_and_its_cells_go_last():
    rows = [{"kind": "x"}, cell("c2"), {"kind": "cell", "cell": "c1", "id": "x"}]
    assert reconcile(rows, ["c1", "c2"]) == [cell("c2"), cell("c1")]


def test_reconcile_is_pure():
    """New values only, inputs untouched, the same input the same output."""
    rows = [strip(["a", "gone"], ["b"], shares=[0.5, 0.5]), cell("a"), strip(["c"])]
    cells = ["c", "b", "a", "d"]
    frozen = copy.deepcopy(rows), list(cells)
    first = reconcile(rows, cells)
    for _ in range(3):
        assert reconcile(rows, cells) == first
    assert (rows, cells) == frozen
    # Nothing in the answer is a piece of the input: changing it changes nothing given.
    kept = reconcile([strip(["a"], ["b"])], ["a", "b"])
    given = [strip(["a"], ["b"])]
    out = reconcile(given, ["a", "b"])
    out[0]["columns"][0]["cells"].append("z")
    assert given == kept


# --- get and set -------------------------------------------------------------------------


async def test_get_reconciles_and_writes_only_when_it_changed(store):
    await plane(store, "p1", "c1", "c2")
    assert await stored(store) is None
    # First read: every cell its own row, healed into the slot.
    assert await get(store) == [cell("c1"), cell("c2")]
    assert await stored(store) == [cell("c1"), cell("c2")]
    # In step: no write. The slot holds the same rows with their keys the other way
    # round, equal as values; a write would put the reconcile's key order back.
    turned = [{"cell": "c1", "kind": "cell"}, {"cell": "c2", "kind": "cell"}]
    await do(store, Web.planes["p1"].layout.set(turned))
    assert await get(store) == [cell("c1"), cell("c2")]
    assert [list(r) for r in await stored(store)] == [["cell", "kind"], ["cell", "kind"]]
    # A cell made with the core op lands last on the next get, one removed goes.
    await do(store, nuspace.cell.add("p1", "x = 1", id="c3", before="c1", fabrics=[]))
    await do(store, nuspace.cell.remove("c1"))
    assert await get(store) == [cell("c2"), cell("c3")]
    assert await stored(store) == [cell("c2"), cell("c3")]


async def test_get_on_a_plane_not_on_the_web_writes_nothing(store):
    await do(store, nuspace.plane.add("bare", backend="async"))
    await do(store, nuspace.cell.add("bare", "x = 1", id="b1", fabrics=[]))
    assert await get(store, "bare") == [cell("b1")]
    assert not await store.read(Web.planes.contains("bare"))
    assert await get(store, "nope") == []


async def test_set_writes_the_rows_reconciled(store):
    await plane(store, "p1", "c1", "c2", "c3")
    rows = [strip(["c3"], ["c1"], shares=[0.4, 0.6]), cell("c2")]
    await do(store, L.set("p1", rows))
    assert await stored(store) == rows
    # Stale rows: a cell gone since, a cell twice, a cell left out, a one cell strip.
    await do(store, nuspace.cell.remove("c3"))
    stale = [strip(["c3"], ["c1"]), cell("c1"), strip(["c9"])]
    await do(store, L.set("p1", stale))
    assert await stored(store) == [cell("c1"), cell("c2")]


async def test_set_refuses_what_it_cannot_do(store):
    await plane(store, "p1", "c1")
    await do(store, nuspace.plane.add("bare", backend="async"))
    refusals = [
        (L.set("nope", []), Missing, "no plane nope"),
        (L.set("bare", []), Missing, "plane bare is not on the web"),
        (L.set("p1", [{"kind": "x"}]), Refused, "row 0 kind"),
        (L.set("p1", [strip(["c1"], ["c2"], shares=[0.9, 0.9])]), Refused, "shares"),
    ]
    for term, exc, said in refusals:
        with pytest.raises(exc, match=said):
            await do(store, term)
    assert await stored(store) is None
    assert not await store.read(Web.planes.contains("bare"))
    await do(store, nuspace.plane.remove("p1"))
    with pytest.raises(Removed):
        await do(store, L.set("p1", []))


# --- transfer ----------------------------------------------------------------------------


async def test_transfer_brings_the_cell_then_sets_the_targets_rows(store):
    await plane(store, "p1", "c1", "c2")
    await plane(store, "p2", "d1", "d2")
    # Beside a cell on the target: a strip made there in the same drop.
    rows = [strip(["d1"], ["c1"]), cell("d2")]
    await store.run(L.transfer("c1", "p2", rows))
    assert await store.read(Space.cells["c1"].plane) == "p2"
    assert await stored(store, "p2") == rows
    # The old plane heals on its next get.
    assert await get(store, "p1") == [cell("c2")]
    # Into a column, under a cell.
    rows = [strip(["d1", "c2"], ["c1"]), cell("d2")]
    await store.run(L.transfer("c2", "p2", rows))
    assert shown(await get(store, "p2")) == [[["d1", "c2"], ["c1"]], "d2"]
    assert await get(store, "p1") == []


async def test_a_failed_transfer_writes_nothing_and_a_failed_set_keeps_the_transfer(store):
    await plane(store, "p1", "c1", "c2")
    await plane(store, "p2", "d1")
    await do(store, nuspace.plane.add("sys", backend="async", system=True))
    await do(store, web.add("sys", editable=True))
    with pytest.raises(Refused):
        await store.run(L.transfer("c1", "sys", [cell("c1")]))
    assert await store.read(Space.cells["c1"].plane) == "p1"
    with pytest.raises(Refused, match="row 0"):
        await store.run(L.transfer("c1", "p2", [{"kind": "x"}]))
    assert await store.read(Space.cells["c1"].plane) == "p2"
    assert await get(store, "p2") == [cell("d1"), cell("c1")]


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

#: How long a pane is left to settle before its ships are counted.
SETTLE = 0.3

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

    def ships(plane: str = "p1") -> int:
        return len(session.pane(plane, "set_cells"))

    def last(plane: str = "p1") -> dict:
        return session.pane(plane, "set_cells")[-1]

    def view(plane: str = "p1") -> list:
        return shown(last(plane)["layout"])

    async def settled() -> int:
        await asyncio.sleep(SETTLE)
        return ships()

    try:
        await _until(lambda: session.frames, BOOT_TIMEOUT)
        session.notify(("viewer", "ops", "planes.open"), {"plane_ids": ["p1", "p2"], "params": {}})
        await _until(lambda: session.pane("p1", "set_cells") and session.pane("p2", "set_cells"))
        # Cells and layout in one write; the open healed the slot.
        assert [c["id"] for c in last()["cells"]] == ["c1", "c2", "c3"]
        assert view() == ["c1", "c2", "c3"]
        assert await stored(store) == [cell("c1"), cell("c2"), cell("c3")]
        heads = len(session.pane("p1", "set_head"))
        # The heal's own write reships once, and that get writes nothing: no loop.
        shipped = await settled()
        assert shipped <= 2
        assert await settled() == shipped

        # layout.set: one write, one reship, its get finds nothing to heal.
        session.notify((*P1, "layout.set"), {"rows": [cell("c3"), strip(["c1"], ["c2"])]})
        await _until(lambda: view() == ["c3", [["c1"], ["c2"]]])
        assert await settled() == shipped + 1
        assert await store.read(nu.list(Space.planes["p1"].cells.keys())) == ["c1", "c2", "c3"]
        # Stale rows are reconciled: c9 is no cell, c3 left out goes last.
        session.notify((*P1, "layout.set"), {"rows": [strip(["c1"], ["c2", "c9"])]})
        await _until(lambda: view() == [[["c1"], ["c2"]], "c3"])
        shipped = await settled()

        # A core cell add: the version reships, get heals (the cell last), the heal reships.
        await do(store, nuspace.cell.add("p1", "x = 1", id="c4", fabrics=[]))
        await _until(lambda: view() == [[["c1"], ["c2"]], "c3", "c4"])
        assert await settled() <= shipped + 2
        shipped = await settled()
        assert await settled() == shipped
        # A removed cell goes, by the strip rules.
        await do(store, nuspace.cell.remove("c2"))
        await _until(lambda: view() == ["c1", "c3", "c4"])

        # cell.create: the browser's id and its rows, the cell under c1 in a column.
        rows = [strip(["c1", "c5"], ["c3"]), cell("c4")]
        session.notify((*P1, "cell.create"), {"cell_id": "c5", "name": "", "rows": rows})
        await _until(lambda: view() == [[["c1", "c5"], ["c3"]], "c4"])
        # An id taken: Exists, nothing else written.
        session.notify((*P1, "cell.create"), {"cell_id": "c5", "name": "", "rows": []})
        await _until(lambda: len(session.toasts()) == 1)
        assert session.toasts()[-1]["type"] == "Exists"

        # layout.transfer: to the other pane, beside its cell, a strip made there.
        session.notify(
            (*P1, "layout.transfer"),
            {"cell_id": "c4", "plane_id": "p2", "rows": [strip(["c4"], ["d1"])]},
        )
        await _until(lambda: view("p2") == [[["c4"], ["d1"]]] and "c4" not in view())
        assert view() == [[["c1", "c5"], ["c3"]]]
        # No layout write ever reshipped the head.
        assert len(session.pane("p1", "set_head")) == heads

        # Refusals toast, the arm keeps listening.
        toasts = len(session.toasts())
        refused = [
            ("layout.set", {"rows": [{"kind": "x"}]}, "Refused"),
            ("layout.set", {}, "ValueError"),
            ("layout.transfer", {"cell_id": "c1", "plane_id": "nope", "rows": []}, "Missing"),
            ("layout.transfer", {"cell_id": "c1", "plane_id": "p2"}, "ValueError"),
            ("cell.create", {"cell_id": "c6", "name": ""}, "ValueError"),
        ]
        for n, (op, payload, kind) in enumerate(refused, start=toasts + 1):
            session.notify((*P1, op), payload)
            await _until(lambda n=n: len(session.toasts()) == n)
            assert session.toasts()[-1]["type"] == kind, (op, session.toasts()[-1])
        # The malformed create and transfer wrote nothing.
        assert not await store.read(Space.cells.contains("c6"))
        assert await store.read(Space.cells["c1"].plane) == "p1"
        session.notify((*P1, "layout.set"), {"rows": [cell("c3")]})
        await _until(lambda: view() == ["c3", "c1", "c5"])
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
