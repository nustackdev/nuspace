"""The store layout: roots, records, named slots, views, and a fresh space's stores made at open.

Build-only checks first (slots and views), then the stores on both backends:
init makes every fixed container and the root plane once, refuses another
format, and the named slots at dynamic levels read and write by plain
navigation.
"""

from __future__ import annotations

import pickle
import sqlite3
import subprocess
import sys

import pytest
from virtuals.container import ContainerNotFoundError

import nu
import nustd.kv
from nu.lang import is_null
from nuspace.devices.web.shapes import RECENTS_CAP, Conn, Pane, Tab, Web, WebPlane
from nuspace.devices.web.stores import CONN_STORE, WEB_STORE
from nuspace.errors import Refused
from nuspace.host.stores import SPACE_STORE, STATE_STORE, init_live
from nuspace.shapes import (
    FORMAT,
    OUT_CAP,
    ROOT,
    Cell,
    CellRun,
    Info,
    Live,
    Plane,
    PlaneRun,
    Space,
    State,
    Worker,
)


#: Run every ``store`` test on both backends: in memory, and the space's sqlite files.
STORES = ("memory", "sqlite")

HISTORY = Space.exec.indexes.history.plane_to_plane_runs
LIVE = Space.exec.indexes.live


class Counter(nu.Shape):
    """A program's own shape, as a cell declares it: no scope base."""

    value = nustd.kv.IntRef.slot()


class Note(nu.Shape):
    """A content item's shape."""

    body = nustd.kv.StrRef.slot()


def slots(shape: type[nu.Shape]) -> set[str]:
    return set(shape._slots)


# --- Layout ---------------------------------------------------------------------------------


def test_each_store_has_its_own_root_file_and_channel():
    stores = (SPACE_STORE, STATE_STORE, WEB_STORE, CONN_STORE)
    assert [(s.root, s.file, s.channel) for s in stores] == [
        (Space, "store/space.db", "nuspace.space"),
        (State, "store/state.db", "nuspace.state"),
        (Web, "devices/web/web_state.db", "nuspace.web"),
        (Conn, "devices/web/conn.db", "nuspace.conn"),
    ]


def test_a_devices_stores_load_without_the_host():
    """The host opens the devices, never the other way round: a fresh import keeps them apart."""
    check = (
        "import sys, nuspace.devices.web.stores; "
        "sys.exit(any(m.startswith('nuspace.host') for m in sys.modules))"
    )
    assert subprocess.run([sys.executable, "-c", check], check=False).returncode == 0  # noqa: S603


def test_the_roots_and_records_carry_the_slots_of_the_data_model():
    lifecycle = {"created_at", "modified_at", "removed_at", "removed_by"}
    common = {"name", "key", "version", "spec", "meta", *lifecycle}
    assert slots(Space) == {"info", "planes", "cells", "indexes", "exec"}
    assert slots(Info) == {"format", "path", "created_at", "opened_at"}
    assert slots(Plane) == common | {
        "icon",
        "parent",
        "cells",
        "children",
        "system",
        "backend",
    }
    assert slots(Cell) == common | {"prog", "fabrics", "plane"}
    ran = {"exit", "error", "created_at", "started_at", "ended_at"}
    assert slots(PlaneRun) == ran | {
        "plane",
        "backend",
        "by",
        "envs",
        "interrupt_at",
        "kill_at",
    }
    assert slots(CellRun) == ran | {
        "plane_run",
        "cell",
        "version",
        "by",
        "worker",
        "out",
        "interrupt_at",
    }
    assert slots(Worker) == ran | {"backend", "plane_run", "handle"}
    assert slots(State) == {
        "cells",
        "planes",
        "space",
        "content_cells",
        "content_planes",
        "content_space",
    }
    assert slots(Web) == {"planes", "pinned", "recents"}
    assert slots(WebPlane) == {"editable", "full_width", "compact"}
    assert slots(Tab) == {"order", "panes", "expanded"}
    assert slots(Pane) == {"params", "plane_run", "restart"}


def test_every_collection_gets_the_view_that_fits_how_it_is_read():
    kv = nustd.kv
    run = HISTORY["p"].runs["r"]
    picked = {
        # point-read records and indexes: plain dicts
        "planes": (Space.planes, kv.DictRef),
        "plane_keys": (Space.indexes.plane_keys, kv.DictRef),
        "cell_runs": (Space.exec.cell_runs, kv.DictRef),
        "web planes": (Web.planes, kv.DictRef),
        "panes": (Conn.connections["s"].panes, kv.DictRef),
        # uncapped user-ordered lists
        "plane cells": (Space.planes["p"].cells, kv.OrderedDictRef),
        "children": (Space.planes["p"].children, kv.OrderedDictRef),
        # append-only paged lists
        "spec_planes": (Space.indexes.spec_planes["s"].ids, kv.LogDictRef),
        "spec_cells": (Space.indexes.spec_cells["s"].ids, kv.LogDictRef),
        "removed": (Space.indexes.removed, kv.LogDictRef),
        "runs": (HISTORY["p"].runs, kv.LogDictRef),
        "cell runs in a run": (run.cell_to_cell_runs["c"].ids, kv.LogDictRef),
        "workers in a run": (run.workers, kv.LogDictRef),
        # live sets and folds: dicts of bool
        "live plane runs": (LIVE.plane_runs, kv.DictRef),
        "live workers": (LIVE.workers, kv.DictRef),
        "expanded": (Conn.connections["s"].expanded, kv.DictRef),
        # small user lists
        "pinned": (Web.pinned, kv.ListRef),
        "recents": (Web.recents, kv.ListRef),
        "order": (Conn.connections["s"].order, kv.ListRef),
        # a capped log
        "out": (Space.exec.cell_runs["cr"].out, kv.RingRef),
    }
    for keyed in (
        "plane_to_plane_runs",
        "cell_to_cell_runs",
        "plane_run_to_cell_runs",
        "plane_run_to_failed_cells",
        "plane_run_to_workers",
    ):
        picked[keyed] = (getattr(LIVE, keyed)["x"].ids, kv.DictRef)
    wrong = {
        name: type(ref).__name__ for name, (ref, view) in picked.items() if type(ref) is not view
    }
    assert wrong == {}
    assert RECENTS_CAP == 50


def test_a_placed_state_chain_routes_to_the_state_store_and_survives_a_pickle():
    placed = Counter.value.with_parent(State.cells["c1"])
    assert nu.shape.root_shape(placed) is State
    back = pickle.loads(pickle.dumps(placed))  # noqa: S301 -- our own term, as a worker gets it
    assert nu.shape.root_shape(back) is State


# --- A fresh space -------------------------------------------------------------------------


async def test_a_fresh_space_gets_its_format_and_every_fixed_container(store):
    info = await store.read(Space.info.extract())
    assert info["format"] == FORMAT
    assert isinstance(info["created_at"], float)
    empty = [
        Space.planes["nothing"].exists(),
        Space.cells.contains("nothing"),
        nu.Not(Space.indexes.spec_planes),
        nu.Not(Space.indexes.spec_cells),
        nu.Not(Space.indexes.plane_keys),
        nu.Not(Space.indexes.cell_keys),
        nu.Not(Space.indexes.removed),
        nu.Not(Space.exec.plane_runs),
        nu.Not(Space.exec.cell_runs),
        nu.Not(Space.exec.workers),
        nu.Not(HISTORY),
        *(nu.Not(getattr(LIVE, name)) for name in Live._slots),
        nu.Not(State.cells),
        nu.Not(State.planes),
        nu.Not(State.content_cells),
        nu.Not(State.content_planes),
        nu.Not(State.content_space),
        nu.Not(Web.planes),
        nu.Not(Web.pinned),
        nu.Not(Web.recents),
        nu.Not(Conn.connections),
    ]
    assert await store.read(nu.List.of(*empty)) == [False, False, *([True] * (len(empty) - 2))]
    assert await store.read(State.space.exists()) is True


async def test_the_root_plane_is_made_once_system_with_no_parent_and_no_backend(store):
    root = await store.read(Space.planes[ROOT].extract())
    assert root.pop("created_at") == root.pop("modified_at")
    assert root == {
        "name": "",
        "key": "",
        "icon": "",
        "parent": "",
        "version": 0,
        "cells": {},
        "children": {},
        "system": True,
        "backend": "",
        "spec": "",
        "meta": {},
    }
    assert await store.read(nu.list(Space.planes.keys())) == [ROOT]


async def test_init_again_keeps_what_is_there(store):
    created = await store.read(Space.info.created_at)
    await store.run(
        nustd.kv.atomic(
            Space.planes[ROOT].children.set_item("p1", True)
            >> Space.planes[ROOT].name.set("top")
            >> Space.indexes.plane_keys.set_item("notes", "p1")
        )
        >> nustd.kv.atomic(Web.pinned.append("p1"))
    )
    await store.run(nustd.kv.atomic(SPACE_STORE.init()) >> nustd.kv.atomic(WEB_STORE.init()))
    assert await store.read(Space.info.created_at) == created
    assert await store.read(nu.list(Space.planes[ROOT].children.keys())) == ["p1"]
    assert await store.read(Space.planes[ROOT].name) == "top"
    assert await store.read(Space.indexes.plane_keys["notes"]) == "p1"
    assert await store.read(Web.pinned.iter().to_list()) == ["p1"]


async def test_a_store_of_another_format_is_refused(store):
    await store.run(nustd.kv.atomic(Space.info.format.set(FORMAT + 1)))
    with pytest.raises(Refused, match="another store format"):
        await store.run(nustd.kv.atomic(SPACE_STORE.init()))
    assert await store.read(Space.info.format) == FORMAT + 1


async def test_live_cleared_at_open_is_made_again_empty(store):
    await store.run(
        nustd.kv.atomic(
            LIVE.plane_runs.set_item("r1", True)
            >> LIVE.plane_run_to_cell_runs["r1"].ids.set_item("cr1", True)
            >> LIVE.workers.set_item("w1", True)
        )
    )
    await store.run(nustd.kv.atomic(Space.exec.indexes.live.erase()))
    assert await store.read(LIVE.plane_runs.exists()) is False
    await store.run(nustd.kv.atomic(init_live()))
    assert await store.read(nu.List.of(*(nu.Not(getattr(LIVE, n)) for n in Live._slots))) == [
        True
    ] * len(Live._slots)


async def test_the_store_files_sit_where_the_layout_says(disk):
    root = disk.path
    for store in (SPACE_STORE, STATE_STORE, WEB_STORE, CONN_STORE):
        with sqlite3.connect(f"{root}/{store.file}") as db:
            assert db.execute("select count(*) from sqlite_master").fetchone()[0] > 0
    assert await disk.read(Space.info.format) == FORMAT


# --- Named slots at dynamic levels -----------------------------------------------------------


async def test_history_is_plane_then_its_runs_then_a_cell_in_one_run(store):
    p = HISTORY["p1"]
    await store.run(
        nustd.kv.atomic(
            p.runs["r1"].cell_to_cell_runs["c1"].ids.set_item("cr1", True)
            >> p.runs["r1"].workers.set_item("w1", True)
            >> p.runs["r2"].cell_to_cell_runs["c1"].ids.set_item("cr3", True)
            >> p.runs["r1"].cell_to_cell_runs["c1"].ids.set_item("cr2", True)
            >> p.runs["r1"].cell_to_cell_runs["c2"].ids.set_item("cr4", True)
        )
    )
    assert await store.read(p.runs.keys(limit=10)) == ["r1", "r2"]
    assert await store.read(p.runs.reversed_keys(limit=1)) == ["r2"]
    cells = p.runs["r1"].cell_to_cell_runs
    assert await store.read(cells["c1"].ids.keys(limit=10)) == ["cr1", "cr2"]
    assert await store.read(cells["c1"].ids.last()) == "cr2"
    assert await store.read(nu.list(p.runs["r1"].workers.keys())) == ["w1"]
    assert sorted(await store.read(nu.list(cells.keys()))) == ["c1", "c2"]
    # A plane never run has no node: the newest run is the default asked for, else a raise.
    assert is_null(await store.read(HISTORY["p9"].runs.last(default=nu.NullForm())))
    with pytest.raises(ContainerNotFoundError):
        await store.read(HISTORY["p9"].runs.last())


async def test_live_sets_add_drop_and_read_empty_in_one_seek(store):
    runs = LIVE.plane_run_to_cell_runs["r1"].ids
    await store.run(nustd.kv.atomic(runs.set_item("cr1", True) >> runs.set_item("cr2", True)))
    await store.run(nustd.kv.atomic(runs.del_item("cr1")))
    assert await store.read(nu.list(runs.keys())) == ["cr2"]
    await store.run(nustd.kv.atomic(runs.del_item("cr2")))
    assert await store.read(nu.Not(runs)) is True
    with pytest.raises(KeyError):
        await store.run(nustd.kv.atomic(runs.del_item("cr2")))


async def test_the_newest_plane_of_a_spec_is_one_seek(store):
    made = Space.indexes.spec_planes["nulog.board"].ids
    await store.run(nustd.kv.atomic(made.set_item("p1", True) >> made.set_item("p2", True)))
    assert await store.read(made.last()) == "p2"
    assert await store.read(Space.indexes.spec_planes["never"].ids.last(default="")) == ""


async def test_a_programs_shape_sits_on_a_scope_through_with_parent(store):
    mine = Counter.value.with_parent(State.cells["c1"])
    theirs = Counter.value.with_parent(State.cells["c2"])
    shared = Counter.value.with_parent(State.planes["p1"])
    space = Counter.value.with_parent(State.space)
    await store.run(nustd.kv.atomic(mine.set(1) >> theirs.set(2) >> shared.set(3) >> space.set(4)))
    assert await store.read(nu.List.of(mine, theirs, shared, space)) == [1, 2, 3, 4]
    assert await store.read(State.cells.extract()) == {"c1": {"value": 1}, "c2": {"value": 2}}


async def test_a_key_read_from_space_places_a_state_chain(store):
    by_key = Counter.value.with_parent(State.cells[Space.indexes.cell_keys["summary"]])
    await store.run(nustd.kv.atomic(Space.indexes.cell_keys.set_item("summary", "c7")))
    await store.run(nustd.kv.atomic(by_key.set(5)))
    assert await store.read(Counter.value.with_parent(State.cells["c7"])) == 5
    gone = Counter.value.with_parent(State.cells[Space.indexes.cell_keys["gone"]])
    assert is_null(await store.read(gone))
    with pytest.raises(nustd.kv.NullAddressError):
        await store.run(nustd.kv.atomic(gone.set(1)))


async def test_content_sits_kind_first_then_place_then_content_key(store):
    kind = "testing.Note"
    at_cell = State.content_cells[kind].cells["c1"].entries
    at_plane = State.content_planes[kind].planes["p1"].entries
    at_space = State.content_space[kind].entries
    await store.run(
        nustd.kv.atomic(
            Note.body.with_parent(at_cell["title"]).set("cell")
            >> Note.body.with_parent(at_plane["title"]).set("plane")
            >> Note.body.with_parent(at_space["readme"]).set("space")
        )
    )
    assert await store.read(State.content_cells.extract()) == {
        kind: {"cells": {"c1": {"entries": {"title": {"body": "cell"}}}}}
    }
    assert await store.read(nu.list(at_plane.keys())) == ["title"]
    assert await store.read(Note.body.with_parent(at_space["readme"])) == "space"


async def test_a_cell_runs_output_keeps_the_last_entries(store):
    out = Space.exec.cell_runs["cr1"].out
    lines = [[float(i), "stdout", f"line {i}"] for i in range(OUT_CAP + 5)]
    await store.run(nustd.kv.atomic(out.extend(lines)))
    kept = await store.read(out.iter().to_list())
    assert len(kept) == OUT_CAP
    assert kept[0] == lines[5]
    assert kept[-1] == lines[-1]


async def test_a_tab_keeps_its_pane_order_apart_from_each_panes_data(store):
    tab = Conn.connections["s1"]
    await store.run(
        nustd.kv.atomic(
            tab.order.set(["p1", "p2"])
            >> tab.panes["p1"].params.set({"row": "r1"})
            >> tab.panes["p1"].plane_run.set("run1")
            >> tab.panes["p2"].restart.set("t1")
            >> tab.expanded.set_item("p1", True)
        )
    )
    await store.run(nustd.kv.atomic(tab.order.set(["p2", "p1"])))
    assert await store.read(tab.order.iter().to_list()) == ["p2", "p1"]
    assert await store.read(tab.panes["p1"].params) == {"row": "r1"}
    assert is_null(await store.read(tab.panes["p2"].plane_run))
    assert await store.read(tab.expanded.contains("p1")) is True
