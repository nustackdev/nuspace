"""The web device without a server or a browser.

What can be checked in process: the session env builds a body that pickles,
a worker unpickling it imports no web server, the device's term compiles and
validates, and the feeds' pure reads (sidebar rows, viewer plane and
statuses) answer the right dicts against a store written through ops.
"""

from __future__ import annotations

import asyncio
import pickle
import subprocess
import sys

import nu
import nustd.ui
from nuspace import ops
from nuspace.ops import TEXT, Plane, Snippet
from nuspace.ops.utils import atomic
from nuspace.shapes import (
    EXIT_FAILED,
    EXIT_KILLED,
    EXIT_OK,
    EXIT_STOPPED,
    STATUS_DEAD,
    STATUS_STARTING,
    STATUS_STOPPING,
    STATUS_UP,
    Space,
)
from nuspace.system.devices.web import CellRoot, SessionWrap, Shell, session_env
from nuspace.system.devices.web.sidebar import create, move, registered_entries, rows
from nuspace.system.devices.web.viewer import plane_view, statuses
from nuspace.system.kernel import build_body
from nustd.ui.core import OP_NOTIFY, Frame, WsSession
from nustd.ui.core.session import Session


PROSE_SRC = "def out():\n    return prose()\n"


PLANES = [
    Plane("plain", "Plain"),
    Plane("jobs", "Jobs", icon="list", cells=(("list", PROSE_SRC),)),
]
SNIPPETS = [
    Snippet(TEXT, "Text", PROSE_SRC),
    Snippet("program", "Program", "def out():\n    return nu.Noop()\n"),
]


# --- The session env -------------------------------------------------------------


def _body():
    """A run body built the way dispatch builds it, inside the session env."""
    env = session_env("127.0.0.1:9")("conn-7")
    return env, build_body("r1", "p1", "c1", [env])


def test_session_env_builds_and_pickles():
    env, body = _body()
    assert env.label == "session:conn-7"
    assert isinstance(env.wrap, SessionWrap)
    assert isinstance(env.rewrite, CellRoot)
    # What crosses into the worker: the rewrite rides inside the body.
    assert pickle.loads(pickle.dumps(env.rewrite)) is not None  # noqa: S301
    assert isinstance(pickle.loads(pickle.dumps(body)), nu.Nu)  # noqa: S301


def test_rewrite_roots_bare_ui_under_the_cell():
    rewrite = CellRoot(Shell.viewer, "c1")
    bare = nustd.ui.TextRef("hello").set(nu.Str("hi"))
    rooted = rewrite(bare)
    assert rooted is not bare
    # A store chain is not a ui chain: left alone.
    store = Space.planes["p1"].name.set(nu.Str("x"))
    assert rewrite(store) is store


def test_worker_unpickling_imports_no_web_server(tmp_path):
    env, body = _body()
    path = tmp_path / "body.pkl"
    path.write_bytes(pickle.dumps((body, env.rewrite)))
    code = (
        "import pickle, sys\n"
        f"pickle.loads(open({str(path)!r}, 'rb').read())\n"
        "bad = [m for m in ('fastapi', 'uvicorn', 'starlette') if m in sys.modules]\n"
        "print(bad)\n"
        "sys.exit(1 if bad else 0)\n"
    )
    done = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=60
    )
    assert done.returncode == 0, done.stdout + done.stderr


def test_warm_imports_cover_drawing_runs_and_no_web_server():
    code = (
        "import sys\n"
        "from nuspace.system.kernel.space import Warmed\n"
        "Warmed().setup(None)\n"
        "light = ('fastapi', 'uvicorn', 'starlette', 'nustd.ws_server')\n"
        "warm = ('nustd.ui', 'nuspace.system.devices.web.env')\n"
        "bad = [m for m in light if m in sys.modules]\n"
        "bad += [m for m in warm if m not in sys.modules]\n"
        "print(bad)\n"
        "sys.exit(1 if bad else 0)\n"
    )
    done = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=60
    )
    assert done.returncode == 0, done.stdout + done.stderr


def test_device_term_compiles_and_validates():
    from nuspace.system.devices.web import serve_web

    term, envs = serve_web(planes=PLANES, snippets=SNIPPETS, open_browser=False, port=0)
    assert set(envs) == {"session"}
    assert envs["session"]("s1").label == "session:s1"
    nu.validate(nu.compile(term))


# --- Sidebar rows ------------------------------------------------------------------


async def _plane(store, pid, name, meta=None, **props):
    await store.run(ops.add_plane(pid, name=name, meta=meta, **props))


def _row(pid, title, parent="space", children=(), made_by="", icon="", system=False):
    return {
        "id": pid,
        "kind": "plane",
        "title": title,
        "parent": parent,
        "children": list(children),
        "made_by": made_by,
        "icon": icon,
        "system": system,
    }


async def test_sidebar_rows_are_one_tree(store):
    await _plane(store, "p1", "One", ui=True, made_by="plain")
    await _plane(store, "p2", "Two", ui=True, made_by="jobs", parent="p1")
    await _plane(store, "p3", "Hidden", ui=False)
    # A drawn plane under a hidden one is lifted to the top, after the rest.
    await _plane(store, "p4", "Lifted", ui=True, parent="p3")
    await _plane(store, "p5", "System", ui=True, system=True)
    await _plane(store, "p6", "Kid", ui=True, parent="p1")
    await _plane(store, "p7", "Bare")
    # Meta is free: keys named like props mean nothing to the sidebar.
    await _plane(store, "p9", "Meta", {"ui": True, "made_by": "plain"})
    # Sibling order is the node's, not creation order.
    await store.run(ops.move_plane("p6", parent="p1", index=0))

    got = await store.read(rows())

    assert got == [
        {
            "id": "space",
            "kind": "space",
            "title": "",
            "parent": "space",
            "children": ["p1", "p5", "p4"],
        },
        _row("p1", "One", children=["p6", "p2"], made_by="plain"),
        _row("p2", "Two", parent="p1", made_by="jobs"),
        _row("p4", "Lifted"),
        # System only protects it: a system ui plane is listed like any other,
        # flagged so the browser offers no delete.
        _row("p5", "System", system=True),
        _row("p6", "Kid", parent="p1"),
    ]


async def test_sidebar_rows_carry_the_icon_and_no_other_meta(store):
    await _plane(store, "p1", "One", {"icon": "emoji:\U0001f680", "tone": "calm"}, ui=True)
    await _plane(store, "p2", "Two", ui=True, made_by="jobs")
    await store.run(ops.set_plane_icon("p2", "lucide:folder"))
    await _plane(store, "p3", "Three", {"icon": 7}, ui=True)

    _, *planes = await store.read(rows())

    assert planes == [
        _row("p1", "One", icon="emoji:\U0001f680"),
        _row("p2", "Two", made_by="jobs", icon="lucide:folder"),
        # Whatever is stored reads as a string; the browser falls back on a bad one.
        _row("p3", "Three", icon="7"),
    ]


async def test_sidebar_rows_empty(store):
    await _plane(store, "p1", "One")
    got = await store.read(rows())
    assert got == [{"id": "space", "kind": "space", "title": "", "parent": "space", "children": []}]


def test_registered_entries():
    assert registered_entries(PLANES) == [
        {"name": "plain", "label": "Plain", "icon": "", "description": ""},
        {"name": "jobs", "label": "Jobs", "icon": "list", "description": ""},
    ]


async def test_create_makes_the_named_plane(store):
    await _plane(store, "top", "Top", ui=True)
    await store.run(create(PLANES, nu.Str("jobs"), nu.Str("pj"), nu.Str("top"), nu.Str("")))
    await store.run(create(PLANES, nu.Str("nope"), nu.Str("px"), nu.Str("space"), nu.Str("X")))
    by_id = {row["id"]: row for row in await store.read(ops.plane_rows())}
    # An empty title takes the label, the parent is the one asked for.
    assert (by_id["pj"]["name"], by_id["pj"]["parent"]) == ("Jobs", "top")
    assert by_id["pj"]["props"] == {"system": False, "ui": True, "made_by": "jobs"}
    assert [c["name"] for c in await store.read(ops.cell_rows("pj"))] == ["list"]
    # An unknown name creates the first registered Plane, at the root.
    assert (by_id["px"]["name"], by_id["px"]["parent"]) == ("X", "root")
    assert by_id["px"]["props"]["made_by"] == "plain"
    # The registered Plane's icon is the new plane's.
    assert by_id["pj"]["meta"] == {"icon": "lucide:list"}
    assert by_id["px"]["meta"] == {}
    assert create([], "x", "y", "z", "w") is None


async def test_move_counts_drawn_siblings_only(store):
    await _plane(store, "a", "A", ui=True)
    await _plane(store, "hidden", "H")
    await _plane(store, "b", "B", ui=True)
    await _plane(store, "c", "C", ui=True)
    # Drawn at the top: a, b, c. Index 1 is before b, whatever sits between.
    await store.run(move(nu.Str("c"), nu.Str("space"), nu.Int(1)))
    assert await store.read(ops.children()) == ["a", "hidden", "c", "b"]
    # Past the end, or negative, is the end.
    await store.run(move(nu.Str("a"), nu.Str(""), nu.Int(9)))
    assert await store.read(ops.children()) == ["hidden", "c", "b", "a"]
    await store.run(move(nu.Str("c"), nu.Str("b"), nu.Int(-1)))
    assert await store.read(ops.children("b")) == ["c"]
    # Into its own subtree: refused, nothing moves.
    await store.run(move(nu.Str("b"), nu.Str("c"), nu.Int(0)))
    assert await store.read(ops.children()) == ["hidden", "b", "a"]


# --- Viewer plane ------------------------------------------------------------------


async def test_viewer_plane(store):
    await _plane(store, "p1", "Notes", {"editable": True, "tone": "calm"}, ui=True)
    await store.run(ops.insert_snippet("p1", SNIPPETS[0], cell_id="c1"))
    await store.run(ops.rename_cell("p1", "c1", "intro"))
    await store.run(ops.add_cell("p1", "x = 1", cell_id="c2", name="code"))
    await store.run(ops.add_cell("p1", "y = 2", cell_id="c0", name="first", index=0))

    got = await store.read(plane_view("p1"))

    assert got == {
        "title": "Notes",
        "meta": {"editable": True, "full_width": False, "tone": "calm"},
        "cells": [
            {"id": "c0", "name": "first", "source": "y = 2", "made_by": ""},
            {"id": "c1", "name": "intro", "source": PROSE_SRC, "made_by": "text"},
            {"id": "c2", "name": "code", "source": "x = 1", "made_by": ""},
        ],
    }


async def test_viewer_plane_missing_and_meta_defaults(store):
    await _plane(store, "p1", "Plain")
    plain = {"editable": False, "full_width": False}
    assert await store.read(plane_view("p1")) == {"title": "Plain", "meta": plain, "cells": []}
    assert await store.read(plane_view("nope")) == {"title": "", "meta": plain, "cells": []}


# --- Viewer statuses ---------------------------------------------------------------


def _run(rid, cell, status, exit_="", error="", *, plane="p1"):
    """A run record as the kernel writes it."""
    row = Space.kernel.runs[rid]
    writes = (
        row.plane.set(plane)
        >> row.cell.set(cell)
        >> row.worker.set("w1")
        >> row.status.set(status)
        >> row.exit.set(exit_)
        >> row.error.set(error)
    )
    if status != STATUS_DEAD:
        writes = writes >> Space.kernel.live.set_item(rid, nu.Str("w1"))
    return atomic(writes)


async def test_viewer_statuses(store):
    cells = [
        "none",
        "start",
        "up",
        "stopping",
        "ok",
        "stopped",
        "killed",
        "failed",
        "mixed",
        "redo",
    ]
    await _plane(store, "p1", "Runs")
    for cell in cells:
        await store.run(ops.add_cell("p1", "x", cell_id=cell))
    await _plane(store, "p2", "Other")
    await store.run(ops.add_cell("p2", "x", cell_id="up"))

    for term in [
        _run("r_01", "start", STATUS_STARTING),
        _run("r_02", "up", STATUS_UP),
        _run("r_03", "stopping", STATUS_STOPPING),
        _run("r_04", "ok", STATUS_DEAD, EXIT_OK),
        _run("r_05", "stopped", STATUS_DEAD, EXIT_STOPPED),
        _run("r_06", "killed", STATUS_DEAD, EXIT_KILLED),
        _run("r_07", "failed", STATUS_DEAD, EXIT_FAILED, "ValueError: boom"),
        # A live run wins over a later dead one.
        _run("r_08", "mixed", STATUS_UP),
        _run("r_09", "mixed", STATUS_DEAD, EXIT_FAILED, "old"),
        # No live run: the most recent one says.
        _run("r_10", "redo", STATUS_DEAD, EXIT_FAILED, "first"),
        _run("r_11", "redo", STATUS_DEAD, EXIT_OK),
        # Another plane's run of a same named cell is not this plane's.
        _run("r_12", "none", STATUS_UP, plane="p2"),
    ]:
        await store.run(term)

    got = await store.read(statuses("p1"))

    def entry(cell, state, error=""):
        return {"cell_id": cell, "state": state, "error": error, "started_at": 0}

    assert got == [
        entry("none", "idle"),
        entry("start", "starting"),
        entry("up", "running"),
        entry("stopping", "running"),
        entry("ok", "idle"),
        entry("stopped", "stopped"),
        entry("killed", "stopped"),
        entry("failed", "failed", "ValueError: boom"),
        entry("mixed", "running"),
        entry("redo", "idle"),
    ]


# --- Connections ---------------------------------------------------------------------


async def test_connections_open_close_clear(store):
    from nuspace.system.devices.web.device import (
        clear_connections,
        close_connection,
        open_connection,
    )

    conns = Space.connections
    await store.run(open_connection("s1") >> open_connection("s2"))
    assert sorted(await store.read(nu.list(conns.keys()))) == ["s1", "s2"]
    assert await store.read(conns["s1"].routes) == []
    assert isinstance(await store.read(conns["s1"].opened), float)

    await store.run(close_connection("s1") >> close_connection("gone"))
    assert await store.read(nu.list(conns.keys())) == ["s2"]

    await store.run(clear_connections())
    assert await store.read(nu.list(conns.keys())) == []
    # Nothing to clear is fine too.
    await store.run(clear_connections())


# --- A connection, live, over a fake session ----------------------------------------


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


async def _until(check, timeout: float = 3.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not check():
        assert asyncio.get_running_loop().time() < deadline, "timed out"
        await asyncio.sleep(0.01)


async def test_connection_live(store):
    from nuspace.system.devices.web.device import connection

    await _plane(store, "p1", "Notes", {"editable": True}, ui=True, made_by="plain")
    await store.run(ops.add_cell("p1", "x = 1", cell_id="c1", name="one"))
    session = FakeSession()
    ctx = store.ctx.bind(Session, session)
    task = asyncio.create_task(
        nu.arun(connection(nu.Str("s1"), planes=PLANES, snippets=SNIPPETS), ctx)
    )
    conns = Space.connections
    try:
        # Boot, the connection published, the sidebar shipped.
        await _until(lambda: session.writes("set_tree"))
        assert session.frames[0].op == "remove"
        viewer_init = next(f for f in session.frames if f.ref == ("viewer",))
        assert viewer_init.chain[0][2]["snippets"] == [
            {"name": "text", "label": "Text"},
            {"name": "program", "label": "Program"},
        ]
        sidebar_init = next(f for f in session.frames if f.ref == ("sidebar",))
        assert sidebar_init.chain[0][2]["registered"] == registered_entries(PLANES)
        assert [row["id"] for row in session.writes("set_tree")[-1]["planes"]] == ["space", "p1"]
        assert await store.read(conns["s1"].routes) == []

        # planes.open: deduped with order kept, empty ids dropped, the plane shipped.
        session.notify(("viewer", "ops", "planes.open"), {"plane_ids": ["p1", "", "p1"]})
        await _until(lambda: session.writes("set_status"))
        assert await store.read(conns["s1"].routes) == ["p1"]
        assert session.writes("set_status")[-1]["plane_id"] == "p1"
        shown = session.writes("set_plane")[-1]
        assert shown["plane_id"] == "p1" and shown["title"] == "Notes"
        assert shown["meta"] == {"editable": True, "full_width": False}
        assert "editable" not in shown
        assert [c["id"] for c in shown["cells"]] == ["c1"]
        assert session.writes("set_status")[-1]["statuses"][0]["state"] == "idle"

        # A cell added reships the plane, a run moving reships the statuses.
        await store.run(ops.add_cell("p1", "y = 2", cell_id="c2"))
        await _until(lambda: len(session.writes("set_plane")[-1]["cells"]) == 2)
        await store.run(_run("r_01", "c1", STATUS_UP))
        await _until(lambda: session.writes("set_status")[-1]["statuses"][0]["state"] == "running")

        # State and output writes wake nothing.
        shipped, stats = len(session.writes("set_plane")), len(session.writes("set_status"))
        trees = len(session.writes("set_tree"))
        await store.run(atomic(Space.planes["p1"].state.set_item("text", nu.Str("hi"))))
        await store.run(atomic(Space.kernel.runs["r_01"].out.set(nu.Literal([[1.0, "out", "x"]]))))
        await asyncio.sleep(0.2)
        assert len(session.writes("set_plane")) == shipped
        assert len(session.writes("set_status")) == stats
        assert len(session.writes("set_tree")) == trees

        # plane.meta merges into meta, reships the plane, and never reaches props.
        # A missing plane is ignored.
        session.notify(
            ("viewer", "ops", "plane.meta"),
            {"plane_id": "p1", "meta": {"full_width": True, "ui": False, "system": True}},
        )
        session.notify(("viewer", "ops", "plane.meta"), {"plane_id": "nope", "meta": {"x": 1}})
        await _until(lambda: session.writes("set_plane")[-1]["meta"]["full_width"])
        assert session.writes("set_plane")[-1]["meta"] == {
            "editable": True,
            "full_width": True,
            "ui": False,
            "system": True,
        }
        (row,) = [r for r in await store.read(ops.plane_rows()) if r["id"] == "p1"]
        assert row["props"] == {"system": False, "ui": True, "made_by": "plain"}
        assert await store.read(ops.plane_exists("nope")) is False

        # Browser events run ops. A create stores the named snippet's prog, an
        # unknown name a blank program.
        session.notify(
            ("viewer", "ops", "cell.create"),
            {"plane_id": "p1", "cell_id": "c3", "name": "text", "index": 0},
        )
        await _until(lambda: session.writes("set_plane")[-1]["cells"][0]["id"] == "c3")
        made = session.writes("set_plane")[-1]["cells"][0]
        assert made["name"] == "text" and made["source"] == PROSE_SRC
        assert made["made_by"] == "text"
        session.notify(
            ("viewer", "ops", "cell.create"),
            {"plane_id": "p1", "cell_id": "c4", "name": "nope", "index": 0},
        )
        await _until(lambda: session.writes("set_plane")[-1]["cells"][0]["id"] == "c4")
        blank = session.writes("set_plane")[-1]["cells"][0]
        assert blank["source"] == "" and blank["made_by"] == ""
        session.notify(
            ("sidebar", "ops", "plane.create"),
            {"plane_id": "p2", "parent_id": "p1", "made_by": "jobs", "title": "Two"},
        )
        await _until(lambda: "p2" in [r["id"] for r in session.writes("set_tree")[-1]["planes"]])
        assert [c["name"] for c in await store.read(ops.cell_rows("p2"))] == ["list"]
        session.notify(("sidebar", "ops", "plane.rename"), {"plane_id": "p2", "title": "Deux"})
        await _until(
            lambda: (
                _row("p2", "Deux", parent="p1", made_by="jobs", icon="lucide:list")
                in session.writes("set_tree")[-1]["planes"]
            )
        )
        # An icon set from the sidebar reships the tree with it.
        session.notify(("sidebar", "ops", "plane.icon"), {"plane_id": "p2", "icon": "emoji:\u2728"})
        await _until(
            lambda: (
                _row("p2", "Deux", parent="p1", made_by="jobs", icon="emoji:\u2728")
                in session.writes("set_tree")[-1]["planes"]
            )
        )
        # A move reparents and reships the tree, a delete drops the plane.
        session.notify(
            ("sidebar", "ops", "plane.move"), {"plane_id": "p2", "parent_id": "space", "index": 0}
        )
        await _until(
            lambda: session.writes("set_tree")[-1]["planes"][0]["children"] == ["p2", "p1"]
        )
        session.notify(("sidebar", "ops", "plane.delete"), {"plane_id": "p2"})
        await _until(
            lambda: "p2" not in [r["id"] for r in session.writes("set_tree")[-1]["planes"]]
        )
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    # Every way out drops the connection.
    assert await store.read(nu.list(conns.keys())) == []


async def test_connection_panes(store):
    from nuspace.system.devices.web.device import connection

    await _plane(store, "p1", "One", ui=True, made_by="plain")
    await _plane(store, "p2", "Two", ui=True, made_by="plain")
    await store.run(ops.add_cell("p1", "x = 1", cell_id="a1"))
    await store.run(ops.add_cell("p2", "y = 2", cell_id="b1"))
    session = FakeSession()
    ctx = store.ctx.bind(Session, session)
    task = asyncio.create_task(
        nu.arun(connection(nu.Str("s1"), planes=PLANES, snippets=SNIPPETS), ctx)
    )
    conns = Space.connections

    def shown() -> dict:
        return {w["plane_id"]: w for w in session.writes("set_plane")}

    def with_status() -> set:
        return {w["plane_id"] for w in session.writes("set_status")}

    try:
        await _until(lambda: session.writes("set_tree"))
        # Two panes: each gets its own plane and statuses, keyed by plane_id.
        session.notify(("viewer", "ops", "planes.open"), {"plane_ids": ["p2", "p1"]})
        await _until(lambda: {"p1", "p2"} <= with_status())
        assert await store.read(conns["s1"].routes) == ["p2", "p1"]
        got = shown()
        assert (got["p1"]["title"], [c["id"] for c in got["p1"]["cells"]]) == ("One", ["a1"])
        assert (got["p2"]["title"], [c["id"] for c in got["p2"]["cells"]]) == ("Two", ["b1"])

        # A change on one plane reships only its pane.
        before = len(session.writes("set_plane"))
        await store.run(ops.add_cell("p1", "z = 3", cell_id="a2"))
        await _until(lambda: len(shown()["p1"]["cells"]) == 2)
        assert {w["plane_id"] for w in session.writes("set_plane")[before:]} == {"p1"}

        # Closing p2: its cells erased as drawn, p1's left alone, nothing more shipped for p2.
        session.notify(("viewer", "ops", "planes.open"), {"plane_ids": ["p1"]})
        await _until(
            lambda: any(
                f.op == "remove" and f.ref == ("viewer", "cells", "b1") for f in session.frames
            )
        )
        assert not any(
            f.op == "remove" and f.ref in {("viewer", "cells"), ("viewer", "cells", "a1")}
            for f in session.frames
        )
        assert await store.read(conns["s1"].routes) == ["p1"]
        await asyncio.sleep(0.05)
        before = len(session.writes("set_plane"))
        await store.run(ops.add_cell("p2", "w = 4", cell_id="b2"))
        await store.run(ops.add_cell("p1", "v = 5", cell_id="a3"))
        await _until(lambda: len(shown()["p1"]["cells"]) == 3)
        assert {w["plane_id"] for w in session.writes("set_plane")[before:]} == {"p1"}

        # No pane open: an empty list closes the last one.
        session.notify(("viewer", "ops", "planes.open"), {"plane_ids": []})
        await _until(
            lambda: any(
                f.op == "remove" and f.ref == ("viewer", "cells", "a1") for f in session.frames
            )
        )
        assert await store.read(conns["s1"].routes) == []
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
