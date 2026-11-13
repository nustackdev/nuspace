"""The web device without a server or a browser.

What can be checked in process: the session env builds a body that pickles,
a worker unpickling it imports no web server, the device's term compiles and
validates, the feeds' reads (sidebar rows, viewer plane and statuses) answer
the right dicts against a store written through ops, and one tab, live over
a fake session: events run ops, store changes ship, and a failed event
toasts.
"""

from __future__ import annotations

import asyncio
import pickle
import subprocess
import sys

from _support.made import MADE
from _support.specs import TEXT_SRC

import nu
import nuspace
import nuspace.web as web
import nustd.ui
from nu.lang import wire
from nuspace.kernel import build_body
from nuspace.ops.plane import DEFAULT_ICON
from nuspace.shapes import EXIT_FAILED, EXIT_INTERRUPTED, EXIT_OK, Space
from nuspace.specs import space_registry
from nuspace.web.env import SessionWrap, session_env
from nuspace.web.planes import ensure
from nuspace.web.shapes import Web
from nuspace.web.shell import Shell
from nuspace.web.sidebar import registered_entries, rows
from nuspace.web.utils import CellRoot
from nuspace.web.viewer import PROGRAM, plane_cells, plane_head, slash_entries, statuses, trail
from nustd.ui.core import OP_NOTIFY, Frame, WsSession
from nustd.ui.core.session import Session


#: The tests' PlaneSpecs and CellSpecs, as a space registers them (``_support.specs``).
REGISTRY = space_registry(extensions=["testing"])
PLANES = list(REGISTRY.planes.values())
CELLS = list(REGISTRY.cells.values())

#: The text CellSpec's registered name, what a cell made from it records as ``spec``.
TEXT = "testing.text"


async def do(store, term):
    return await store.run(nuspace.atomic(term))


async def plane(store, pid, name="", *, parent="root", on_web=True, **kw):
    await do(store, nuspace.plane.add(pid, name=name, parent=parent, backend="async", **kw))
    if on_web:
        await do(store, web.add(pid, editable=True))


# --- The session env -------------------------------------------------------------


def _body():
    """A run body built the way the kernel builds it, inside the session env."""
    env = session_env("127.0.0.1:9")("tab-7")
    return env, build_body("r1", "cr1", "p1", "c1", [env])


def test_session_env_builds_and_pickles():
    env, body = _body()
    assert env.label == "session:tab-7"
    assert isinstance(env.wrap, SessionWrap)
    assert isinstance(env.rewrite, CellRoot)
    assert pickle.loads(pickle.dumps(env.rewrite)) is not None  # noqa: S301
    assert isinstance(wire.loads(wire.dumps(body)), nu.Nu)


def test_rewrite_roots_bare_ui_under_the_cell():
    rewrite = CellRoot(Shell.viewer, "c1")
    bare = nustd.ui.TextRef("hello").set(nu.Str("hi"))
    assert rewrite(bare) is not bare
    # A store chain is not a ui chain: left alone.
    stored = Space.planes["p1"].name.set(nu.Str("x"))
    assert rewrite(stored) is stored


async def test_a_cells_refs_land_in_a_column_with_no_gap():
    """The cell's own node holds what it draws and adds no spacing of its own."""
    rooted = CellRoot(Shell.viewer, "c1")(nustd.ui.TextRef("t").set("hi"))
    session = FakeSession()
    await nu.arun(rooted, nu.Context().bind(Session, session))
    (frame,) = session.frames
    cell = next(step for step in frame.chain if step[0] == "c1")
    assert cell[1] == "Column" and cell[2] == {"gap": 0}
    assert tuple(frame.ref) == ("viewer", "cells", "c1", "t")


def test_worker_unpickling_imports_no_web_server(tmp_path):
    env, body = _body()
    path = tmp_path / "body.pkl"
    path.write_bytes(wire.dumps((body, env.rewrite)))
    code = (
        "import pickle, sys\n"
        "import nuspace.web\n"
        f"pickle.loads(open({str(path)!r}, 'rb').read())\n"
        "bad = [m for m in ('uvicorn', 'starlette') if m in sys.modules]\n"
        "print(bad)\n"
        "sys.exit(1 if bad else 0)\n"
    )
    done = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=60
    )
    assert done.returncode == 0, done.stdout + done.stderr


def test_device_term_compiles_and_validates():
    from nuspace.web.device import serve_web

    term, envs = serve_web(registry=REGISTRY, open_browser=False, port=0, static=None)
    assert set(envs) == {"session"}
    assert envs["session"]("s1").label == "session:s1"
    nu.validate(nu.compile(term))


# --- Sidebar rows ------------------------------------------------------------------


def _row(pid, title, parent="space", children=(), spec="", icon=DEFAULT_ICON, system=False):
    return {
        "id": pid,
        "kind": "plane",
        "title": title,
        "parent": parent,
        "children": list(children),
        "spec": spec,
        "icon": icon,
        "system": system,
    }


async def _rows(store, sid):
    """The tab's rows as the sidebar ships them, read in one snapshot."""
    return await store.made(nuspace.atomic(rows(sid, into=MADE)))


async def test_sidebar_rows_are_lazy(store):
    await plane(store, "p1", "One")
    await plane(store, "p2", "Two", parent="p1", icon="emoji:🎬")
    await plane(store, "p3", "Three", parent="p2")
    await plane(store, "off", "Off", on_web=False)
    await plane(store, "under", "Under", parent="off")
    await do(store, web.open_tab("t"))
    got = await _rows(store, "t")
    assert got == [
        {"id": "space", "kind": "space", "title": "", "parent": "space", "children": ["p1"]},
        _row("p1", "One"),
    ]
    await do(store, web.expand("t", "p1"))
    got = await _rows(store, "t")
    assert got[1:] == [
        _row("p1", "One", children=["p2"]),
        _row("p2", "Two", parent="p1", icon="emoji:🎬"),
    ]
    await do(store, web.expand("t", "p2"))
    got = await _rows(store, "t")
    assert _row("p3", "Three", parent="p2") in got


async def test_sidebar_skips_removed_and_ships_no_row_off_the_walk(store):
    await plane(store, "p1", "One")
    await plane(store, "deep", "Deep", parent="p1")
    await plane(store, "gone", "Gone")
    await do(store, nuspace.plane.remove("gone"))
    await do(store, web.open_tab("t"))
    got = await _rows(store, "t")
    # deep hangs under a closed branch: no row.
    assert [r["id"] for r in got] == ["space", "p1"]


async def test_sidebar_walks_only_branches_under_shipped_rows(store):
    await plane(store, "p1", "One")
    await plane(store, "p2", "Two", parent="p1")
    await plane(store, "p3", "Three", parent="p2")
    await plane(store, "off", "Off", on_web=False)
    await plane(store, "under", "Under", parent="off")
    await plane(store, "gone", "Gone")
    await plane(store, "left", "Left", parent="gone")
    await do(store, web.open_tab("t"))
    for p in ("p1", "p2", "off", "gone"):
        await do(store, web.expand("t", p))
    await do(store, nuspace.plane.remove("gone"))
    got = await _rows(store, "t")
    assert [r["id"] for r in got] == ["space", "p1", "p2", "p3"]
    # p1 closed: p2 is no row, so its open branch lists nothing.
    await do(store, web.collapse("t", "p1"))
    got = await _rows(store, "t")
    assert got[1:] == [_row("p1", "One")]


def test_registered_entries():
    assert registered_entries(PLANES) == [
        {"name": "testing.plain", "label": "Plain", "group": "", "icon": "", "description": ""},
        {"name": "testing.jobs", "label": "Jobs", "group": "", "icon": "list", "description": ""},
    ]


# --- Viewer reads ------------------------------------------------------------------


async def test_viewer_head_and_cells(store):
    await plane(store, "p1", "Notes", icon="lucide:book", key="notes")
    await do(store, web.set("p1", width="full"))
    await do(store, nuspace.cell.add("p1", "x = 1", id="c1", name="one", fabrics=["ui"]))
    await do(store, nuspace.specs.add_cell("p1", TEXT, id="c2", fabrics=[]))
    assert await store.read(plane_head("p1")) == {
        "absent": "",
        "title": "Notes",
        "icon": "lucide:book",
        "key": "notes",
        "system": False,
        "editable": True,
        "width": "full",
    }
    assert await store.read(plane_cells("p1", CELLS)) == [
        {
            "id": "c1",
            "name": "one",
            "key": "",
            "source": "x = 1",
            "spec": "",
            "draws": True,
            "classes": [],
        },
        {
            "id": "c2",
            "name": "text",
            "key": "",
            "source": TEXT_SRC,
            "spec": TEXT,
            "draws": False,
            "classes": ["prose"],
        },
    ]


async def test_viewer_head_absent(store):
    await plane(store, "off", on_web=False)
    await plane(store, "gone")
    await do(store, nuspace.plane.remove("gone"))
    assert (await store.read(plane_head("nope")))["absent"] == "missing"
    assert (await store.read(plane_head("gone")))["absent"] == "missing"
    assert (await store.read(plane_head("off")))["absent"] == "headless"
    await store.run(ensure())
    home = await store.read(Web.roles["home"])
    assert (await store.read(plane_head(home)))["system"] is True


async def test_viewer_trail_climbs_whatever_the_sidebar_shows(store):
    await plane(store, "p1", "One")
    await plane(store, "p2", "Two", parent="p1")
    await plane(store, "p3", "Three", parent="p2")
    # No tab, nothing expanded: the trail does not read the sidebar.
    got = await store.made(nuspace.atomic(trail("p3", into=MADE)))
    assert got == [{"id": "p1", "title": "One"}, {"id": "p2", "title": "Two"}]
    assert await store.made(nuspace.atomic(trail("p1", into=MADE))) == []
    assert await store.made(nuspace.atomic(trail("nope", into=MADE))) == []


def test_slash_entries_ship_classes_and_one_default_per_class():
    entries = slash_entries(CELLS)
    assert entries[0]["name"] == TEXT
    assert entries[0]["classes"] == ["prose"] and entries[0]["default_for"] == ["prose"]


async def test_viewer_statuses(store):
    await plane(store, "p1")
    for c in ("c1", "c2", "c3", "c4"):
        await do(store, nuspace.cell.add("p1", "x = 1", id=c, fabrics=[]))
    from _support.made import MADE

    run = await store.made(nuspace.atomic(nuspace.plane_run.add("p1", into=MADE)))
    assert [s["state"] for s in await store.read(statuses("p1", ""))] == ["idle"] * 4
    made = {}
    for c in ("c1", "c2", "c3"):
        made[c] = await store.made(nuspace.atomic(nuspace.cell_run.add(run, c, into=MADE)))
    await do(store, nuspace.cell_run.start(made["c2"], worker="w"))
    await do(store, nuspace.cell_run.start(made["c3"], worker="w"))
    await do(store, nuspace.cell_run.end(made["c3"], EXIT_FAILED, "boom"))
    got = {s["cell_id"]: s for s in await store.read(statuses("p1", run))}
    assert got["c1"]["state"] == "starting"
    assert got["c2"]["state"] == "running" and got["c2"]["started_at"] > 0
    assert got["c3"]["state"] == "failed" and got["c3"]["error"] == "boom"
    assert got["c4"]["state"] == "idle"
    await do(store, nuspace.cell_run.end(made["c2"], EXIT_INTERRUPTED))
    await do(store, nuspace.cell_run.end(made["c1"], EXIT_OK))
    got = {s["cell_id"]: s for s in await store.read(statuses("p1", run))}
    assert got["c2"]["state"] == "stopped" and got["c1"]["state"] == "idle"


# --- A tab, live, over a fake session ----------------------------------------


class FakeSession(WsSession):
    """A session with no socket: frames sent are kept, notifies are fired by hand."""

    def __init__(self) -> None:
        super().__init__(ws=None)
        self.frames: list[Frame] = []

    async def send(self, frame: Frame) -> None:
        self.frames.append(frame)

    def notify(self, path: tuple[str, ...], payload: dict) -> None:
        self._dispatch(Frame(OP_NOTIFY, ref=path, payload=payload))

    def writes(self, op: str) -> list[dict]:
        return [
            f.payload
            for f in self.frames
            if isinstance(f.payload, dict) and f.payload.get("op") == op
        ]

    def pane(self, plane: str, op: str) -> list[dict]:
        """The writes of ``op`` on the pane's own node, in order."""
        at = ("viewer", "panes", plane)
        return [p for p in self.writes(op) if self._ref_of(p) == at]

    def erased(self, *path: str) -> bool:
        """Whether a ``remove`` went out for ``path``."""
        return any(f.op == "remove" and tuple(f.ref) == path for f in self.frames)

    def _ref_of(self, payload: dict) -> tuple[str, ...]:
        return next(tuple(f.ref) for f in self.frames if f.payload is payload)

    def toasts(self) -> list[dict]:
        return [f.payload for f in self.frames if f.ref == ("toast",) and f.payload]


#: Where the pane on p1 hears its events.
PANE = ("viewer", "panes", "p1", "ops")


# A tab compiles and validates its whole term before the first frame, which
# can take seconds on a loaded machine. Reactions after boot keep the short timeout.
BOOT_TIMEOUT = 30.0


async def _until(check, timeout: float = 3.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not check():
        assert asyncio.get_running_loop().time() < deadline, "timed out"
        await asyncio.sleep(0.01)


async def _until_store(store, read, timeout: float = 3.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not await store.read(read):
        assert asyncio.get_running_loop().time() < deadline, "timed out"
        await asyncio.sleep(0.02)


def _tree(session):
    return {r["id"]: r for r in session.writes("set_tree")[-1]["planes"]}


async def test_tab_live(store):
    from nuspace.web.device import connection

    await plane(store, "p1", "Notes")
    await do(store, nuspace.cell.add("p1", "x = 1", id="c1", name="one", fabrics=[]))
    session = FakeSession()
    ctx = store.ctx.bind(Session, session)
    task = asyncio.create_task(nu.arun(connection(nu.Str("s1"), registry=REGISTRY), ctx))
    tabs = web.Conn.connections

    def on(op):
        return ("viewer", "panes", "p1", "ops", op)

    def cells():
        return session.pane("p1", "set_cells")[-1]["cells"]

    try:
        # Boot: the tab's row, the shell seeded, the sidebar shipped.
        await _until(lambda: session.writes("set_tree"), BOOT_TIMEOUT)
        assert session.frames[0].op == "remove"
        assert {f.ref for f in session.frames if f.op == "init"} >= {
            ("sidebar",),
            ("viewer",),
            ("toast",),
            ("desks",),
        }
        assert list(_tree(session)) == ["space", "p1"]
        assert await store.read(nu.list(tabs["s1"].order)) == []

        # planes.open: the panes written, the pane's head, cells and statuses shipped, a visit.
        session.notify(
            ("viewer", "ops", "planes.open"), {"plane_ids": ["p1"], "params": {"p1": {"q": "x"}}}
        )
        await _until(lambda: session.pane("p1", "set_status") and session.pane("p1", "set_cells"))
        await _until(lambda: session.pane("p1", "set_head"))
        assert await store.read(nu.list(tabs["s1"].order)) == ["p1"]
        assert await store.read(tabs["s1"].panes["p1"].params) == {"q": "x"}
        assert await store.read(nu.list(web.Web.recents)) == ["p1"]
        head = session.pane("p1", "set_head")[-1]
        assert head == {
            "op": "set_head",
            "title": "Notes",
            "icon": DEFAULT_ICON,
            "key": "",
            "system": False,
            "editable": True,
            "width": "page",
        }
        assert [c["id"] for c in cells()] == ["c1"]
        assert session.pane("p1", "set_status")[-1]["statuses"][0]["state"] == "idle"
        assert "plane_id" not in session.pane("p1", "set_status")[-1]

        # Pane events run ops on the pane's own path: a cell from a spec, a
        # starter cell, a move, web flags.
        session.notify(on("cell.create"), {"cell_id": "c2", "name": TEXT, "before": "c1"})
        await _until(lambda: cells()[0]["id"] == "c2")
        assert cells()[0]["source"] == TEXT_SRC and cells()[0]["spec"] == TEXT
        session.notify(on("cell.create"), {"cell_id": "c3", "name": ""})
        await _until(lambda: cells()[-1]["id"] == "c3")
        assert cells()[-1]["source"] == PROGRAM
        session.notify(on("cell.move"), {"cell_id": "c3", "before": "c2"})
        await _until(lambda: cells()[0]["id"] == "c3")
        session.notify(on("cell.update"), {"cell_id": "c1", "source": "y = 2"})
        await _until(lambda: any(c["source"] == "y = 2" for c in cells()))
        session.notify(on("plane.web"), {"flags": {"width": "board"}})
        await _until(lambda: session.pane("p1", "set_head")[-1]["width"] == "board")
        # A cell's key: set, changed and removed, each reshipped.
        session.notify(on("cell.key"), {"cell_id": "c1", "key": "first"})
        await _until(lambda: any(c["key"] == "first" for c in cells()))
        session.notify(on("cell.key"), {"cell_id": "c1", "key": "one-1"})
        await _until(lambda: any(c["key"] == "one-1" for c in cells()))
        assert await store.read(Space.indexes.cell_keys.contains("first")) is False
        session.notify(on("cell.remove_key"), {"cell_id": "c1"})
        await _until(lambda: all(c["key"] == "" for c in cells()))
        assert await store.read(Space.indexes.cell_keys.contains("one-1")) is False
        # The plane's key, the same way: set, changed and removed, each reshipped.
        session.notify(on("plane.key"), {"key": "first"})
        await _until(lambda: session.pane("p1", "set_head")[-1]["key"] == "first")
        session.notify(on("plane.key"), {"key": "notes-1"})
        await _until(lambda: session.pane("p1", "set_head")[-1]["key"] == "notes-1")
        assert await store.read(Space.indexes.plane_keys.contains("first")) is False
        session.notify(on("plane.remove_key"), {})
        await _until(lambda: session.pane("p1", "set_head")[-1]["key"] == "")
        assert await store.read(Space.indexes.plane_keys.contains("notes-1")) is False

        # A rename and an icon reship the head and the trail's readers, never the cells.
        shipped = len(session.pane("p1", "set_cells"))
        session.notify(on("plane.rename"), {"title": "Notes 2"})
        await _until(lambda: session.pane("p1", "set_head")[-1]["title"] == "Notes 2")
        session.notify(on("plane.icon"), {"icon": "emoji:📓"})
        await _until(lambda: session.pane("p1", "set_head")[-1]["icon"] == "emoji:📓")
        await asyncio.sleep(0.2)
        assert len(session.pane("p1", "set_cells")) == shipped
        # A cell edit reships the cells, never the head.
        heads = len(session.pane("p1", "set_head"))
        session.notify(on("cell.update"), {"cell_id": "c1", "source": "y = 3"})
        await _until(lambda: any(c["source"] == "y = 3" for c in cells()))
        await asyncio.sleep(0.2)
        assert len(session.pane("p1", "set_head")) == heads
        assert await store.read(Space.planes["p1"].name) == "Notes 2"

        # Sidebar events: a plane made from a spec under p1, an expand loads it.
        session.notify(
            ("sidebar", "ops", "plane.create"),
            {"plane_id": "p2", "parent_id": "p1", "spec": "testing.jobs", "title": "Two"},
        )
        await _until_store(store, Web.planes.contains("p2"))
        # It hangs under a closed branch: not shipped until p1 opens.
        assert "p2" not in _tree(session)
        session.notify(("sidebar", "ops", "plane.expand"), {"plane_id": "p1"})
        await _until(lambda: "p2" in _tree(session))
        assert _tree(session)["p1"]["children"] == ["p2"]
        assert _tree(session)["p2"]["spec"] == "testing.jobs"
        session.notify(("sidebar", "ops", "plane.rename"), {"plane_id": "p2", "title": "Deux"})
        await _until(lambda: _tree(session)["p2"]["title"] == "Deux")
        session.notify(
            ("sidebar", "ops", "plane.move"),
            {"plane_id": "p2", "parent_id": "space", "before": "p1"},
        )
        await _until(lambda: _tree(session)["space"]["children"] == ["p2", "p1"])
        session.notify(("sidebar", "ops", "plane.delete"), {"plane_id": "p2"})
        await _until(lambda: "p2" not in _tree(session))
        # The tree ships its rows only.
        assert set(session.writes("set_tree")[-1]) == {"op", "planes"}
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    # Every way out drops the tab.
    assert await store.read(tabs.contains("s1")) is False


async def test_a_pane_is_its_own_node(store):
    """Each pane hears its own events, a delete turns it absent, a close erases its node."""
    from nuspace.web.device import connection

    await plane(store, "p1", "One")
    await plane(store, "p2", "Two")
    session = FakeSession()
    ctx = store.ctx.bind(Session, session)
    task = asyncio.create_task(nu.arun(connection(nu.Str("s1"), registry=REGISTRY), ctx))

    def on(plane, op):
        return ("viewer", "panes", plane, "ops", op)

    try:
        await _until(lambda: session.writes("set_tree"), BOOT_TIMEOUT)
        session.notify(("viewer", "ops", "planes.open"), {"plane_ids": ["p1", "p2"], "params": {}})
        await _until(lambda: session.pane("p1", "set_head") and session.pane("p2", "set_head"))
        assert session.pane("p2", "set_trail")[-1] == {"op": "set_trail", "trail": []}

        # p2's rename on p2's path renames p2 alone, and only p2's head reships.
        p1_heads = len(session.pane("p1", "set_head"))
        session.notify(on("p2", "plane.rename"), {"title": "Deux"})
        await _until(lambda: session.pane("p2", "set_head")[-1]["title"] == "Deux")
        assert await store.read(Space.planes["p1"].name) == "One"
        await asyncio.sleep(0.2)
        assert len(session.pane("p1", "set_head")) == p1_heads

        # A delete from the pane: the plane goes, the pane is told it is missing.
        session.notify(on("p2", "plane.delete"), {})
        await _until(lambda: session.pane("p2", "set_absent"))
        assert session.pane("p2", "set_absent")[-1] == {"op": "set_absent", "reason": "missing"}
        assert await store.read(Space.planes["p2"].removed_at.exists()) is True

        # Closed: its node erased, the other pane's kept.
        session.notify(("viewer", "ops", "planes.open"), {"plane_ids": ["p1"], "params": {}})
        await _until(lambda: session.erased("viewer", "panes", "p2"))
        assert not session.erased("viewer", "panes", "p1")

        # A late event for the closed pane has nobody listening: nothing runs, nothing toasts.
        session.notify(on("p2", "plane.rename"), {"title": "Late"})
        await asyncio.sleep(0.2)
        assert await store.read(Space.planes["p2"].name) == "Deux"
        assert session.toasts() == []
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_a_pane_closed_and_reopened_at_once_is_shipped_again(store):
    """The browser drops a closed pane's node at once: a reopen gets its head and cells again.

    The close and the reopen go back to back, before the server settles, so
    the tab's pane order may read the same before and after.
    """
    from nuspace.web.device import connection

    await plane(store, "p1", "One")
    await plane(store, "p2", "Two")
    session = FakeSession()
    ctx = store.ctx.bind(Session, session)
    task = asyncio.create_task(nu.arun(connection(nu.Str("s1"), registry=REGISTRY), ctx))
    opened = ("viewer", "ops", "planes.open")
    try:
        await _until(lambda: session.writes("set_tree"), BOOT_TIMEOUT)
        session.notify(opened, {"plane_ids": ["p1", "p2"], "params": {}})
        await _until(lambda: session.pane("p1", "set_head") and session.pane("p1", "set_cells"))
        await asyncio.sleep(0.3)
        heads, cells = len(session.pane("p1", "set_head")), len(session.pane("p1", "set_cells"))
        session.notify(opened, {"plane_ids": ["p2"], "params": {}})
        session.notify(opened, {"plane_ids": ["p1", "p2"], "params": {}})
        await _until(lambda: len(session.pane("p1", "set_head")) > heads)
        await _until(lambda: len(session.pane("p1", "set_cells")) > cells)
        # Whatever erase went out for p1 went before its new head.
        last_erase = max(
            (
                i
                for i, f in enumerate(session.frames)
                if f.op == "remove" and tuple(f.ref) == ("viewer", "panes", "p1")
            ),
            default=-1,
        )
        last_head = max(
            i
            for i, f in enumerate(session.frames)
            if isinstance(f.payload, dict)
            and f.payload.get("op") == "set_head"
            and tuple(f.ref) == ("viewer", "panes", "p1")
        )
        assert last_erase < last_head
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_a_cell_made_or_edited_in_a_finished_pane_restarts_it(store):
    """nav starts runs only on open or a restart token: the device asks for one when the run is over."""
    from nuspace.web.device import connection

    await plane(store, "p1", "Notes")
    await do(store, nuspace.cell.add("p1", "x = 1", id="c1", fabrics=[]))
    session = FakeSession()
    ctx = store.ctx.bind(Session, session)
    task = asyncio.create_task(nu.arun(connection(nu.Str("s1"), registry=REGISTRY), ctx))
    pane = web.Conn.connections["s1"].panes["p1"]
    try:
        await _until(lambda: session.writes("set_tree"), BOOT_TIMEOUT)
        session.notify(("viewer", "ops", "planes.open"), {"plane_ids": ["p1"], "params": {}})
        await _until_store(store, web.Conn.connections["s1"].panes.contains("p1"))

        # No run recorded yet: nav is starting one, nothing asked.
        session.notify((*PANE, "cell.update"), {"cell_id": "c1", "source": "x = 2"})
        await _until_store(store, Space.cells["c1"].prog == "x = 2")
        # A live run: reload's to rerun the cell, nothing asked.
        run = await store.made(nuspace.atomic(nuspace.plane_run.add("p1", into=MADE)))
        await do(store, pane.plane_run.set(run))
        session.notify((*PANE, "cell.update"), {"cell_id": "c1", "source": "x = 3"})
        await _until_store(store, Space.cells["c1"].prog == "x = 3")
        await asyncio.sleep(0.2)
        assert await store.read(pane.restart) == ""

        # The run is over: an edit restarts the pane, and so does a new cell.
        await do(store, nuspace.plane_run.end(run, EXIT_OK))
        session.notify((*PANE, "cell.update"), {"cell_id": "c1", "source": "x = 4"})
        await _until_store(store, pane.restart != "")
        first = await store.read(pane.restart)
        session.notify((*PANE, "cell.create"), {"cell_id": "c2", "name": ""})
        await _until_store(store, pane.restart != first)
        assert session.toasts() == []
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_a_failed_event_toasts_its_type_and_message(store):
    from nuspace.web.device import connection

    await plane(store, "p1", "One")
    await store.run(ensure())
    session = FakeSession()
    ctx = store.ctx.bind(Session, session)
    task = asyncio.create_task(nu.arun(connection(nu.Str("s1"), registry=REGISTRY), ctx))
    try:
        await _until(lambda: session.writes("set_tree"), BOOT_TIMEOUT)
        # A refused op: home is a system plane.
        home = await store.read(Web.roles["home"])
        session.notify(("sidebar", "ops", "plane.delete"), {"plane_id": home})
        await _until(lambda: session.toasts())
        (shown,) = session.toasts()
        assert shown["op"] == "show" and shown["type"] == "Refused"
        assert "system plane" in shown["message"]
        # A plane made under an id taken: Exists. The arm kept listening.
        session.notify(
            ("sidebar", "ops", "plane.create"),
            {"plane_id": "p1", "parent_id": "space", "spec": "", "title": ""},
        )
        await _until(lambda: len(session.toasts()) == 2)
        assert session.toasts()[-1]["type"] == "Exists"
        # A malformed event raises and toasts like any other failure.
        session.notify(("sidebar", "ops", "plane.rename"), {"plane_id": "p1"})
        await _until(lambda: len(session.toasts()) == 3)
        assert session.toasts()[-1]["type"] == "ValueError"
        assert "'title'" in session.toasts()[-1]["message"]
        # Pane events need the pane open: they ride its own path.
        session.notify(("viewer", "ops", "planes.open"), {"plane_ids": ["p1"], "params": {}})
        await _until(lambda: session.pane("p1", "set_head"))
        session.notify((*PANE, "plane.web"), {"flags": {"wide": True}})
        await _until(lambda: len(session.toasts()) == 4)
        assert session.toasts()[-1]["type"] == "ValueError"
        # A key taken by another cell, and one not in key chars.
        await do(store, nuspace.cell.add("p1", "x = 1", id="c1", key="taken", fabrics=[]))
        await do(store, nuspace.cell.add("p1", "x = 2", id="c2", fabrics=[]))
        session.notify((*PANE, "cell.key"), {"cell_id": "c2", "key": "taken"})
        await _until(lambda: len(session.toasts()) == 5)
        assert session.toasts()[-1]["type"] == "Exists"
        session.notify((*PANE, "cell.key"), {"cell_id": "c2", "key": "no spaces"})
        await _until(lambda: len(session.toasts()) == 6)
        assert session.toasts()[-1]["type"] == "Refused"
        # A plane key taken by another plane, one not in key chars, and none to remove.
        await plane(store, "p2", key="held")
        session.notify((*PANE, "plane.key"), {"key": "held"})
        await _until(lambda: len(session.toasts()) == 7)
        assert session.toasts()[-1]["type"] == "Exists"
        session.notify((*PANE, "plane.key"), {"key": "no spaces"})
        await _until(lambda: len(session.toasts()) == 8)
        assert session.toasts()[-1]["type"] == "Refused"
        session.notify((*PANE, "plane.remove_key"), {})
        await _until(lambda: len(session.toasts()) == 9)
        assert session.toasts()[-1]["type"] == "Missing"
        # Opening a plane that never lands: told it is missing after the wait, no toast.
        session.notify(("viewer", "ops", "planes.open"), {"plane_ids": ["ghost"], "params": {}})
        await _until(lambda: session.writes("set_absent"), timeout=6.0)
        assert session.pane("ghost", "set_absent")[-1] == {"op": "set_absent", "reason": "missing"}
        # The tab still works.
        heads = len(session.pane("p1", "set_head"))
        session.notify(("viewer", "ops", "planes.open"), {"plane_ids": ["p1"], "params": {}})
        await _until(lambda: len(session.pane("p1", "set_head")) > heads)
        assert len(session.toasts()) == 9
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_a_plane_opened_before_it_lands_is_waited_for(store, monkeypatch):
    """The browser opens a plane while its create is in flight: Space row, then web row."""
    from nuspace.web import device

    # Room for both commits to land well past the wait's early looks.
    monkeypatch.setattr(device, "OPEN_WAIT", 8.0)
    connection = device.connection
    session = FakeSession()
    ctx = store.ctx.bind(Session, session)
    task = asyncio.create_task(nu.arun(connection(nu.Str("s1"), registry=REGISTRY), ctx))
    try:
        await _until(lambda: session.writes("set_tree"), BOOT_TIMEOUT)
        session.notify(("viewer", "ops", "planes.open"), {"plane_ids": ["late"], "params": {}})
        # Past the wait's early looks: what lands from here on is heard.
        await asyncio.sleep(1.5)
        await do(store, nuspace.plane.add("late", name="Late", backend="async"))
        await asyncio.sleep(1.0)
        await do(store, web.add("late"))
        order = web.Conn.connections["s1"].order
        await _until_store(store, nu.list(order) == nu.Literal(["late"]))
        await _until(lambda: session.pane("late", "set_head"))
        assert session.pane("late", "set_head")[-1]["title"] == "Late"
        assert session.toasts() == []
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_a_plane_with_no_view_opens_as_headless_without_the_long_wait(store):
    """Not on the web: the pane is told so right after the short web wait, and nothing toasts."""
    from nuspace.web import device

    await plane(store, "off", on_web=False)
    session = FakeSession()
    ctx = store.ctx.bind(Session, session)
    task = asyncio.create_task(nu.arun(device.connection(nu.Str("s1"), registry=REGISTRY), ctx))
    try:
        await _until(lambda: session.writes("set_tree"), BOOT_TIMEOUT)
        session.notify(("viewer", "ops", "planes.open"), {"plane_ids": ["off"], "params": {}})
        await _until(lambda: session.writes("set_absent"), timeout=device.OPEN_WAIT)
        assert session.pane("off", "set_absent")[-1] == {"op": "set_absent", "reason": "headless"}
        assert await store.read(nu.list(web.Conn.connections["s1"].order)) == ["off"]
        assert session.toasts() == []
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_ensure_makes_the_web_planes_once(store):
    await store.run(ensure())
    roles = await store.read(Web.roles.extract())
    assert set(roles) == {"home", "search", "settings"}
    home = roles["home"]
    await do(store, nuspace.plane.rename(home, "My home"))
    await store.run(ensure())
    assert await store.read(Web.roles.extract()) == roles
    for pid in (*roles.values(), "searches"):
        assert await store.read(Space.planes[pid].system) is True
    assert await store.read(Space.planes[home].name) == "My home"
    assert await store.read(web.Web.planes.contains(home)) is True
    assert await store.read(web.Web.planes.contains("searches")) is False
    cells = await store.read(nu.list(Space.planes[home].cells.keys()))
    names = [await store.read(Space.cells[c].name) for c in cells]
    assert names == ["space", "history", "now"]
