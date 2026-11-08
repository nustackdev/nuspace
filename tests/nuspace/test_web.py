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
import nuspace.devices.web as web
import nustd.ui
from nu.lang import wire
from nuspace.devices.web.env import SessionWrap, session_env
from nuspace.devices.web.planes import ensure
from nuspace.devices.web.shapes import Web
from nuspace.devices.web.shell import Shell
from nuspace.devices.web.sidebar import pins, registered_entries, rows
from nuspace.devices.web.utils import CellRoot
from nuspace.devices.web.viewer import PROGRAM, plane_view, slash_entries, statuses
from nuspace.kernel import build_body
from nuspace.shapes import EXIT_FAILED, EXIT_INTERRUPTED, EXIT_OK, Space
from nuspace.specs import space_registry
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
        "import nuspace.devices.web\n"
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
    from nuspace.devices.web.device import serve_web

    term, envs = serve_web(registry=REGISTRY, open_browser=False, port=0, static=None)
    assert set(envs) == {"session"}
    assert envs["session"]("s1").label == "session:s1"
    nu.validate(nu.compile(term))


# --- Sidebar rows ------------------------------------------------------------------


def _row(pid, title, parent="space", children=(), spec="", icon="", system=False):
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


async def test_sidebar_skips_removed_and_ships_pins_wherever_they_hang(store):
    await plane(store, "p1", "One")
    await plane(store, "deep", "Deep", parent="p1")
    await plane(store, "gone", "Gone")
    await do(store, web.pin("deep"))
    await do(store, web.pin("gone"))
    await do(store, nuspace.plane.remove("gone"))
    await do(store, web.open_tab("t"))
    got = await _rows(store, "t")
    assert [r["id"] for r in got] == ["space", "p1", "deep"]
    assert got[-1] == _row("deep", "Deep", parent="p1")
    assert await store.read(pins()) == ["deep"]


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


async def test_viewer_plane(store):
    await plane(store, "p1", "Notes", icon="lucide:book")
    await do(store, web.set("p1", full_width=True))
    await do(store, nuspace.cell.add("p1", "x = 1", id="c1", name="one", fabrics=["ui"]))
    await do(store, nuspace.specs.add_cell("p1", TEXT, id="c2", fabrics=[]))
    got = await store.read(plane_view("p1", CELLS))
    assert got["absent"] == "" and got["title"] == "Notes"
    assert got["meta"] == {
        "editable": True,
        "full_width": True,
        "compact": False,
        "icon": "lucide:book",
    }
    assert got["cells"] == [
        {"id": "c1", "name": "one", "source": "x = 1", "spec": "", "has_ui": True, "classes": []},
        {
            "id": "c2",
            "name": "text",
            "source": TEXT_SRC,
            "spec": TEXT,
            "has_ui": False,
            "classes": ["prose"],
        },
    ]


async def test_viewer_plane_absent(store):
    await plane(store, "off", on_web=False)
    await plane(store, "gone")
    await do(store, nuspace.plane.remove("gone"))
    assert (await store.read(plane_view("nope")))["absent"] == "missing"
    assert (await store.read(plane_view("gone")))["absent"] == "missing"
    assert (await store.read(plane_view("off")))["absent"] == "headless"


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

    def toasts(self) -> list[dict]:
        return [f.payload for f in self.frames if f.ref == ("toast",) and f.payload]


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
    from nuspace.devices.web.device import connection

    await plane(store, "p1", "Notes")
    await do(store, nuspace.cell.add("p1", "x = 1", id="c1", name="one", fabrics=[]))
    session = FakeSession()
    ctx = store.ctx.bind(Session, session)
    task = asyncio.create_task(nu.arun(connection(nu.Str("s1"), registry=REGISTRY), ctx))
    tabs = web.Conn.connections
    try:
        # Boot: the tab's row, the shell seeded, the sidebar shipped.
        await _until(lambda: session.writes("set_tree"), BOOT_TIMEOUT)
        assert session.frames[0].op == "remove"
        assert {f.ref for f in session.frames if f.op == "init"} >= {
            ("sidebar",),
            ("viewer",),
            ("toast",),
        }
        assert list(_tree(session)) == ["space", "p1"]
        assert await store.read(nu.list(tabs["s1"].order)) == []

        # planes.open: the panes written, the plane and its statuses shipped, a visit.
        session.notify(
            ("viewer", "ops", "planes.open"), {"plane_ids": ["p1"], "params": {"p1": {"q": "x"}}}
        )
        await _until(lambda: session.writes("set_status"))
        assert await store.read(nu.list(tabs["s1"].order)) == ["p1"]
        assert await store.read(tabs["s1"].panes["p1"].params) == {"q": "x"}
        assert await store.read(nu.list(web.Web.recents)) == ["p1"]
        shown = session.writes("set_plane")[-1]
        assert shown["plane_id"] == "p1" and shown["title"] == "Notes"
        assert [c["id"] for c in shown["cells"]] == ["c1"]
        assert session.writes("set_status")[-1]["statuses"][0]["state"] == "idle"

        # Viewer events run ops: a cell from a spec, a starter cell, a move, web flags.
        session.notify(
            ("viewer", "ops", "cell.create"),
            {"plane_id": "p1", "cell_id": "c2", "name": TEXT, "before": "c1"},
        )
        await _until(lambda: session.writes("set_plane")[-1]["cells"][0]["id"] == "c2")
        made = session.writes("set_plane")[-1]["cells"][0]
        assert made["source"] == TEXT_SRC and made["spec"] == TEXT
        session.notify(
            ("viewer", "ops", "cell.create"), {"plane_id": "p1", "cell_id": "c3", "name": ""}
        )
        await _until(lambda: session.writes("set_plane")[-1]["cells"][-1]["id"] == "c3")
        assert session.writes("set_plane")[-1]["cells"][-1]["source"] == PROGRAM
        session.notify(("viewer", "ops", "cell.move"), {"cell_id": "c3", "before": "c2"})
        await _until(lambda: session.writes("set_plane")[-1]["cells"][0]["id"] == "c3")
        session.notify(("viewer", "ops", "cell.update"), {"cell_id": "c1", "source": "y = 2"})
        await _until(
            lambda: any(c["source"] == "y = 2" for c in session.writes("set_plane")[-1]["cells"])
        )
        session.notify(
            ("viewer", "ops", "plane.web"), {"plane_id": "p1", "flags": {"full_width": True}}
        )
        await _until(lambda: session.writes("set_plane")[-1]["meta"]["full_width"])

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
        session.notify(("sidebar", "ops", "plane.pin"), {"plane_id": "p1"})
        await _until(lambda: session.writes("set_tree")[-1]["pinned"] == ["p1"])
        session.notify(("sidebar", "ops", "plane.pin"), {"plane_id": "p2", "before": "p1"})
        await _until(lambda: session.writes("set_tree")[-1]["pinned"] == ["p2", "p1"])
        session.notify(("sidebar", "ops", "plane.pin_move"), {"plane_id": "p2"})
        await _until(lambda: session.writes("set_tree")[-1]["pinned"] == ["p1", "p2"])
        session.notify(("sidebar", "ops", "plane.delete"), {"plane_id": "p2"})
        await _until(lambda: "p2" not in _tree(session))
        assert session.writes("set_tree")[-1]["pinned"] == ["p1"]
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    # Every way out drops the tab.
    assert await store.read(tabs.contains("s1")) is False


async def test_a_failed_event_toasts_its_type_and_message(store):
    from nuspace.devices.web.device import connection

    await plane(store, "p1", "One")
    await store.run(ensure())
    session = FakeSession()
    ctx = store.ctx.bind(Session, session)
    task = asyncio.create_task(nu.arun(connection(nu.Str("s1"), registry=REGISTRY), ctx))
    try:
        await _until(lambda: session.writes("set_tree"), BOOT_TIMEOUT)
        # A refused op: home is a system plane.
        session.notify(("sidebar", "ops", "plane.delete"), {"plane_id": "home"})
        await _until(lambda: session.toasts())
        (shown,) = session.toasts()
        assert shown["op"] == "show" and shown["type"] == "Refused"
        assert "system plane" in shown["message"]
        # A second pin of one plane: Exists. The arm kept listening.
        session.notify(("sidebar", "ops", "plane.pin"), {"plane_id": "p1"})
        session.notify(("sidebar", "ops", "plane.pin"), {"plane_id": "p1"})
        await _until(lambda: len(session.toasts()) == 2)
        assert session.toasts()[-1]["type"] == "Exists"
        # A malformed event raises and toasts like any other failure.
        session.notify(("sidebar", "ops", "plane.rename"), {"plane_id": "p1"})
        await _until(lambda: len(session.toasts()) == 3)
        assert session.toasts()[-1]["type"] == "ValueError"
        assert "'title'" in session.toasts()[-1]["message"]
        session.notify(("viewer", "ops", "plane.web"), {"plane_id": "p1", "flags": {"wide": True}})
        await _until(lambda: len(session.toasts()) == 4)
        assert session.toasts()[-1]["type"] == "ValueError"
        # Opening a plane that never lands: Missing, after the wait for it.
        session.notify(("viewer", "ops", "planes.open"), {"plane_ids": ["ghost"], "params": {}})
        await _until(lambda: len(session.toasts()) == 5, timeout=6.0)
        assert session.toasts()[-1]["type"] == "Missing"
        # Nothing of it landed, and the tab still works.
        session.notify(("viewer", "ops", "planes.open"), {"plane_ids": ["p1"], "params": {}})
        await _until(lambda: session.writes("set_plane"))
        assert len(session.toasts()) == 5
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_a_plane_opened_before_it_lands_is_waited_for(store, monkeypatch):
    """The browser opens a plane while its create is in flight: Space row, then web row."""
    from nuspace.devices.web import device

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
        assert session.toasts() == []
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_ensure_makes_the_web_planes_once(store):
    await store.run(ensure())
    await do(store, nuspace.plane.rename("home", "My home"))
    await store.run(ensure())
    for pid in ("home", "search", "settings", "searches"):
        assert await store.read(Space.planes[pid].system) is True
    assert await store.read(Space.planes["home"].name) == "My home"
    assert await store.read(web.Web.planes.contains("home")) is True
    assert await store.read(web.Web.planes.contains("searches")) is False
    cells = await store.read(nu.list(Space.planes["home"].cells.keys()))
    assert cells == ["home_header", "home_recent", "home_glance", "home_start"]
