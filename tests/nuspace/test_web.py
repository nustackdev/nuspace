"""The web device without a server or a browser.

What can be checked in process: the session env builds a body that pickles,
a worker unpickling it imports no web server, the device's term compiles and
validates, and the feeds' pure reads (sidebar rows, viewer page and
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
from nuspace.ops import App, Snippet
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
from nuspace.system.devices.web.sidebar import create_plane, rows
from nuspace.system.devices.web.viewer import page, statuses
from nuspace.system.kernel import build_body
from nustd.ui.core import OP_NOTIFY, Frame, WsSession
from nustd.ui.core.session import Session


PROSE_SRC = "def out():\n    return prose()\n"


def make_page(kind: str):
    """An app build: a ui plane under ``kind``'s section."""

    def build(plane_id=None, name=""):
        return ops.add_plane(plane_id, name=name, ui=True, made_by=kind)

    return build


APPS = [
    App("page", "Pages", make_page("page")),
    App("job", "Jobs", make_page("job")),
    App("chat", "Chat", make_page("chat"), section=False),
]
SNIPPETS = [
    Snippet("prose", "Text", PROSE_SRC),
    Snippet("program", "Program", "def out():\n    return nu.Noop()\n"),
]


# --- the session env -------------------------------------------------------------


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

    term, envs = serve_web(apps=APPS, snippets=SNIPPETS, open_browser=False, port=0)
    assert set(envs) == {"session"}
    assert envs["session"]("s1").label == "session:s1"
    nu.validate(nu.compile(term))


# --- sidebar rows ------------------------------------------------------------------


async def _plane(store, pid, name, meta=None, **props):
    await store.run(ops.add_plane(pid, name=name, meta=meta, **props))


async def test_sidebar_rows(store):
    await _plane(store, "p1", "One", ui=True, made_by="page")
    await _plane(store, "p2", "Two", ui=True, made_by="job")
    await _plane(store, "p3", "Hidden", ui=False, made_by="page")
    await _plane(store, "p4", "System", ui=True, made_by="page", system=True)
    await _plane(store, "p5", "Chat", ui=True, made_by="chat")
    await _plane(store, "p6", "Stray", ui=True, made_by="nobody")
    await _plane(store, "p7", "Bare")
    await _plane(store, "p8", "Three", ui=True, made_by="page")
    # Meta is free: keys named like props mean nothing to the sidebar.
    await _plane(store, "p9", "Meta", {"ui": True, "made_by": "page"})

    got = await store.read(rows(APPS))

    assert got == [
        {
            "id": "space",
            "kind": "space",
            "title": "",
            "parent": "space",
            "children": ["page", "job"],
        },
        {
            "id": "page",
            "kind": "group",
            "title": "Pages",
            "parent": "space",
            "children": ["p1", "p8"],
        },
        {"id": "job", "kind": "group", "title": "Jobs", "parent": "space", "children": ["p2"]},
        {"id": "p1", "kind": "plane", "title": "One", "parent": "page", "children": []},
        {"id": "p2", "kind": "plane", "title": "Two", "parent": "job", "children": []},
        {"id": "p8", "kind": "plane", "title": "Three", "parent": "page", "children": []},
    ]


async def test_sidebar_rows_with_no_sections(store):
    await _plane(store, "p1", "One", ui=True, made_by="page")
    got = await store.read(rows([]))
    assert got == [{"id": "space", "kind": "space", "title": "", "parent": "space", "children": []}]


async def test_create_runs_the_group_app(store):
    await store.run(create_plane(APPS, nu.Str("job"), nu.Str("pj"), nu.Str("Made")))
    await store.run(create_plane(APPS, nu.Str("chat"), nu.Str("pc"), nu.Str("Fallback")))
    got = await store.read(ops.plane_rows())
    by_id = {row["id"]: row for row in got}
    assert by_id["pj"]["name"] == "Made"
    assert by_id["pj"]["props"]["made_by"] == "job"
    # chat is no section: an unknown group runs the first section app.
    assert by_id["pc"]["props"]["made_by"] == "page"
    assert create_plane([APPS[2]], "x", "y", "z") is None


# --- viewer page -------------------------------------------------------------------


async def test_viewer_page(store):
    await _plane(store, "p1", "Notes", {"editable": True, "tone": "calm"}, ui=True)
    await store.run(ops.add_cell("p1", PROSE_SRC, cell_id="c1", name="intro"))
    await store.run(ops.add_cell("p1", "x = 1", cell_id="c2", name="code"))
    await store.run(ops.add_cell("p1", "y = 2", cell_id="c0", name="first", index=0))

    got = await store.read(page("p1"))

    assert got == {
        "title": "Notes",
        "meta": {"editable": True, "full_width": False, "tone": "calm"},
        "blocks": [
            {"id": "c0", "name": "first", "source": "y = 2"},
            {"id": "c1", "name": "intro", "source": PROSE_SRC},
            {"id": "c2", "name": "code", "source": "x = 1"},
        ],
    }


async def test_viewer_page_missing_and_meta_defaults(store):
    await _plane(store, "p1", "Plain")
    plain = {"editable": False, "full_width": False}
    assert await store.read(page("p1")) == {"title": "Plain", "meta": plain, "blocks": []}
    assert await store.read(page("nope")) == {"title": "", "meta": plain, "blocks": []}


# --- viewer statuses ---------------------------------------------------------------


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
        return {"section_id": cell, "state": state, "error": error, "started_at": 0}

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


# --- connections ---------------------------------------------------------------------


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


# --- a connection, live, over a fake session ----------------------------------------


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

    await _plane(store, "p1", "Notes", {"editable": True}, ui=True, made_by="page")
    await store.run(ops.add_cell("p1", "x = 1", cell_id="c1", name="one"))
    session = FakeSession()
    ctx = store.ctx.bind(Session, session)
    task = asyncio.create_task(nu.arun(connection(nu.Str("s1"), apps=APPS, snippets=SNIPPETS), ctx))
    conns = Space.connections
    try:
        # Boot, the connection published, the sidebar shipped.
        await _until(lambda: session.writes("set_tree"))
        assert session.frames[0].op == "remove"
        viewer_init = next(f for f in session.frames if f.ref == ("viewer",))
        assert viewer_init.chain[0][2]["snippets"] == [
            {"name": s.name, "label": s.label} for s in SNIPPETS
        ]
        assert [row["id"] for row in session.writes("set_tree")[-1]["pages"]] == [
            "space",
            "page",
            "job",
            "p1",
        ]
        assert await store.read(conns["s1"].routes) == []

        # pages.open: deduped with order kept, empty ids dropped, the page shipped.
        session.notify(("viewer", "ops", "pages.open"), {"page_ids": ["p1", "", "p1"]})
        await _until(lambda: session.writes("set_status"))
        assert await store.read(conns["s1"].routes) == ["p1"]
        assert session.writes("set_status")[-1]["page_id"] == "p1"
        shown = session.writes("set_page")[-1]
        assert shown["page_id"] == "p1" and shown["title"] == "Notes"
        assert shown["meta"] == {"editable": True, "full_width": False}
        assert "editable" not in shown
        assert [b["id"] for b in shown["blocks"]] == ["c1"]
        assert session.writes("set_status")[-1]["statuses"][0]["state"] == "idle"

        # A cell added reships the page, a run moving reships the statuses.
        await store.run(ops.add_cell("p1", "y = 2", cell_id="c2"))
        await _until(lambda: len(session.writes("set_page")[-1]["blocks"]) == 2)
        await store.run(_run("r_01", "c1", STATUS_UP))
        await _until(lambda: session.writes("set_status")[-1]["statuses"][0]["state"] == "running")

        # State and output writes wake nothing.
        pages, stats = len(session.writes("set_page")), len(session.writes("set_status"))
        trees = len(session.writes("set_tree"))
        await store.run(atomic(Space.planes["p1"].state.set_item("text", nu.Str("hi"))))
        await store.run(atomic(Space.kernel.runs["r_01"].out.set(nu.Literal([[1.0, "out", "x"]]))))
        await asyncio.sleep(0.2)
        assert len(session.writes("set_page")) == pages
        assert len(session.writes("set_status")) == stats
        assert len(session.writes("set_tree")) == trees

        # page.meta merges into meta, reships the page, and never reaches props.
        # A missing plane is ignored.
        session.notify(
            ("viewer", "ops", "page.meta"),
            {"page_id": "p1", "meta": {"full_width": True, "ui": False, "system": True}},
        )
        session.notify(("viewer", "ops", "page.meta"), {"page_id": "nope", "meta": {"x": 1}})
        await _until(lambda: session.writes("set_page")[-1]["meta"]["full_width"])
        assert session.writes("set_page")[-1]["meta"] == {
            "editable": True,
            "full_width": True,
            "ui": False,
            "system": True,
        }
        (row,) = [r for r in await store.read(ops.plane_rows()) if r["id"] == "p1"]
        assert row["props"] == {"system": False, "ui": True, "made_by": "page"}
        assert await store.read(ops.plane_exists("nope")) is False

        # Browser events run ops. A create stores the named snippet's prog, an
        # unknown name a blank program.
        session.notify(
            ("viewer", "ops", "section.create"),
            {"page_id": "p1", "section_id": "c3", "name": "prose", "index": 0},
        )
        await _until(lambda: session.writes("set_page")[-1]["blocks"][0]["id"] == "c3")
        made = session.writes("set_page")[-1]["blocks"][0]
        assert made["name"] == "prose" and made["source"] == PROSE_SRC
        session.notify(
            ("viewer", "ops", "section.create"),
            {"page_id": "p1", "section_id": "c4", "name": "nope", "index": 0},
        )
        await _until(lambda: session.writes("set_page")[-1]["blocks"][0]["id"] == "c4")
        assert session.writes("set_page")[-1]["blocks"][0]["source"] == ""
        session.notify(
            ("sidebar", "ops", "page.create"), {"page_id": "p2", "group": "job", "title": "Two"}
        )
        await _until(lambda: "p2" in [r["id"] for r in session.writes("set_tree")[-1]["pages"]])
        session.notify(("sidebar", "ops", "page.rename"), {"page_id": "p2", "title": "Deux"})
        await _until(
            lambda: (
                {"id": "p2", "kind": "plane", "title": "Deux", "parent": "job", "children": []}
                in session.writes("set_tree")[-1]["pages"]
            )
        )
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    # Every way out drops the connection.
    assert await store.read(nu.list(conns.keys())) == []


async def test_connection_panes(store):
    from nuspace.system.devices.web.device import connection

    await _plane(store, "p1", "One", ui=True, made_by="page")
    await _plane(store, "p2", "Two", ui=True, made_by="page")
    await store.run(ops.add_cell("p1", "x = 1", cell_id="a1"))
    await store.run(ops.add_cell("p2", "y = 2", cell_id="b1"))
    session = FakeSession()
    ctx = store.ctx.bind(Session, session)
    task = asyncio.create_task(nu.arun(connection(nu.Str("s1"), apps=APPS, snippets=SNIPPETS), ctx))
    conns = Space.connections

    def pages() -> dict:
        return {w["page_id"]: w for w in session.writes("set_page")}

    def status_pages() -> set:
        return {w["page_id"] for w in session.writes("set_status")}

    try:
        await _until(lambda: session.writes("set_tree"))
        # Two panes: each gets its own page and statuses, keyed by page_id.
        session.notify(("viewer", "ops", "pages.open"), {"page_ids": ["p2", "p1"]})
        await _until(lambda: {"p1", "p2"} <= status_pages())
        assert await store.read(conns["s1"].routes) == ["p2", "p1"]
        got = pages()
        assert (got["p1"]["title"], [b["id"] for b in got["p1"]["blocks"]]) == ("One", ["a1"])
        assert (got["p2"]["title"], [b["id"] for b in got["p2"]["blocks"]]) == ("Two", ["b1"])

        # A change on one plane reships only its pane.
        before = len(session.writes("set_page"))
        await store.run(ops.add_cell("p1", "z = 3", cell_id="a2"))
        await _until(lambda: len(pages()["p1"]["blocks"]) == 2)
        assert {w["page_id"] for w in session.writes("set_page")[before:]} == {"p1"}

        # Closing p2: its cells erased as drawn, p1's left alone, nothing more shipped for p2.
        session.notify(("viewer", "ops", "pages.open"), {"page_ids": ["p1"]})
        await _until(
            lambda: any(
                f.op == "remove" and f.ref == ("viewer", "sections", "b1") for f in session.frames
            )
        )
        assert not any(
            f.op == "remove" and f.ref in {("viewer", "sections"), ("viewer", "sections", "a1")}
            for f in session.frames
        )
        assert await store.read(conns["s1"].routes) == ["p1"]
        await asyncio.sleep(0.05)
        before = len(session.writes("set_page"))
        await store.run(ops.add_cell("p2", "w = 4", cell_id="b2"))
        await store.run(ops.add_cell("p1", "v = 5", cell_id="a3"))
        await _until(lambda: len(pages()["p1"]["blocks"]) == 3)
        assert {w["page_id"] for w in session.writes("set_page")[before:]} == {"p1"}

        # No pane open: an empty list closes the last one.
        session.notify(("viewer", "ops", "pages.open"), {"page_ids": []})
        await _until(
            lambda: any(
                f.op == "remove" and f.ref == ("viewer", "sections", "a1") for f in session.frames
            )
        )
        assert await store.read(conns["s1"].routes) == []
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
