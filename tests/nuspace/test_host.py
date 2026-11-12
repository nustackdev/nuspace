"""The host: the registry, where a space lives, the lock, the open's resources, and open_space for real.

The registry is plain python. The layout, the lock and the resources are
file system work, tested on their own. ``make_space`` and ``open_space``
run for real on sqlite with a private notification server: headless, with
real workers, held open while the test reads. Two tests run ``nuspace run``
in a process of its own: one stops it with SIGINT, as Ctrl+C does, one
kills it with SIGKILL, as a crash does.
"""

from __future__ import annotations

import asyncio
import contextlib
import errno
import functools
import os
import signal
import socket
import subprocess
import sys
import time
import warnings
from typing import TYPE_CHECKING

import pytest
from _support.kernel import _Hold
from _support.made import MADE, MADE_STORE

import nu
import nuspace
import nustd.kv
from nuspace import host
from nuspace.errors import Missing, Refused
from nuspace.host import interactions, presets
from nuspace.host import lock as lock_module
from nuspace.host.layout import DATA_DIR, LOCK_FILE, data_dir, find_space, is_older, is_space
from nuspace.host.lock import HostLock, LockWarning, holder
from nuspace.host.resources import DataDir, Fresh, Throwaway
from nuspace.kernel import CLOSED, LEFT_OVER, Env
from nuspace.shapes import EXIT_INTERRUPTED, EXIT_KILLED, FORMAT, Space
from nuspace.specs import (
    GROUP,
    CellSpec,
    Extension,
    PlaneSpec,
    Registry,
    RegistryWarning,
    WebOptions,
    discover,
    registered_name,
    short_name,
    space_registry,
)
from nuspace.specs import registry as registry_module
from nuspace.system import init
from nuspace.web import CONN_STORE, WEB_STORE, Conn, Web


if TYPE_CHECKING:
    from pathlib import Path


def _plane(name: str, label: str = "") -> PlaneSpec:
    return PlaneSpec(name, label or name, backend="async")


def _cell(name: str, source: str = "") -> CellSpec:
    return CellSpec(name, name, source or name)


def _env(label: str):
    return lambda *args: Env(label=label)


class _Point:
    """An entry point: a name, and what loading it gives."""

    def __init__(self, name: str, load) -> None:
        self.name = name
        self._load = load

    def load(self):
        return self._load()


def _points(monkeypatch, points: list[_Point]) -> list[str]:
    asked: list[str] = []

    def entry_points(*, group: str):
        asked.append(group)
        return points

    monkeypatch.setattr(registry_module, "entry_points", entry_points)
    # The installed listing's cache, fresh over the patched points and dropped after.
    fresh = functools.cache(registry_module._installed.__wrapped__)
    monkeypatch.setattr(registry_module, "_installed", fresh)
    return asked


# --- The registry ----------------------------------------------------------------


def test_merge_keeps_the_first_per_name_and_warns():
    first = Extension(
        (_plane("a.plain", "Mine"),), (_cell("a.text", "a"),), (), {"db": _env("mine")}
    )
    second = Extension(
        (_plane("a.plain", "Theirs"), _plane("b.jobs")),
        (_cell("a.text", "b"), _cell("b.heading")),
        (),
        {"db": _env("theirs"), "llm": _env("llm")},
    )
    with pytest.warns(RegistryWarning) as caught:
        reg = Registry.merge({"a": first, "b": second})
    assert len(caught) == 3
    assert "'a.plain' from b ignored: a registered it first" in str(caught[0].message)
    assert list(reg.planes) == ["a.plain", "b.jobs"]
    assert reg.planes["a.plain"].label == "Mine"
    assert reg.cells["a.text"].source == "a"
    assert list(reg.cells) == ["a.text", "b.heading"]
    assert reg.envs["db"]().label == "mine"
    assert set(reg.envs) == {"db", "llm"}


def test_discover_loads_extensions_and_factories_and_skips_the_broken(monkeypatch):
    def broken():
        raise ImportError("no such module")

    ext = Extension(planes=(_plane("plain"),))
    asked = _points(
        monkeypatch,
        [
            _Point("plain", lambda: ext),
            _Point("factory", lambda: lambda: Extension(cells=(_cell("text"),))),
            _Point("broken", broken),
            _Point("wrong", lambda: lambda: 42),
            _Point("plain", lambda: Extension(planes=(_plane("again"),))),
        ],
    )
    with pytest.warns(RegistryWarning) as caught:
        found = discover()
    assert asked == [GROUP]
    assert list(found) == ["plain", "factory"]
    assert [p.name for p in found["plain"].planes] == ["plain.plain"]
    assert [s.name for s in found["factory"].cells] == ["factory.text"]
    said = [str(w.message) for w in caught]
    assert any("'broken' failed to load" in s for s in said)
    assert any("'wrong' is not an Extension: int" in s for s in said)
    assert any("'plain' is installed twice" in s for s in said)


def test_the_host_env_wins_over_an_installed_one(monkeypatch):
    installed = Extension(
        (_plane("plain", "Installed"), _plane("jobs")), (), (), {"db": _env("installed")}
    )
    _points(monkeypatch, [_Point("installed", lambda: installed)])
    with pytest.warns(RegistryWarning) as caught:
        reg = space_registry(envs={"db": _env("host")})
    assert {str(w.message) for w in caught} == {
        "Env 'db' from installed ignored: open_space registered it first",
    }
    assert list(reg.planes) == ["installed.plain", "installed.jobs"]
    assert reg.envs["db"]().label == "host"


def test_installed_planes_are_named_after_their_package(monkeypatch):
    """Two packages may add a plane or a Cell of one short name."""
    _points(
        monkeypatch,
        [
            _Point("tools", lambda: Extension((_plane("chat", "Tools"),), (_cell("text"),))),
            _Point("agents", lambda: Extension((_plane("chat", "Agents"),), (_cell("text"),))),
        ],
    )
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        reg = space_registry()
    assert {n: p.label for n, p in reg.planes.items()} == {
        "tools.chat": "Tools",
        "agents.chat": "Agents",
    }
    assert list(reg.cells) == ["tools.text", "agents.text"]


def test_a_package_spec_knows_the_name_it_registers_under(monkeypatch):
    """What code holding the package's own spec writes as made_by."""
    plane, cell = _plane("chat"), _cell("slider")
    _points(monkeypatch, [_Point("tools", lambda: Extension((plane,), (cell,)))])
    assert registered_name(plane) == "tools.chat"
    assert registered_name(cell) == "tools.slider"
    assert registered_name(_cell("slider")) == "slider"
    reg = space_registry()
    assert registered_name(reg.cells["tools.slider"]) == "tools.slider"
    assert short_name("tools.slider") == short_name("slider") == "slider"


def test_a_space_takes_the_packages_it_names(monkeypatch):
    _points(
        monkeypatch,
        [
            _Point("tools", lambda: Extension((_plane("chat"),))),
            _Point("agents", lambda: Extension((_plane("crew"),), (_cell("text"),))),
        ],
    )
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert list(space_registry(extensions=["agents"]).planes) == ["agents.crew"]
        # Entry point order, whatever order they are named in.
        assert list(space_registry(extensions=["agents", "tools"]).planes) == [
            "tools.chat",
            "agents.crew",
        ]
        none = space_registry(extensions=())
    assert (list(none.planes), list(none.cells)) == ([], [])
    with pytest.raises(LookupError, match="'nobody'"):
        space_registry(extensions=["tools", "nobody"])


def test_the_tests_specs_register_through_their_installed_package():
    reg = space_registry(extensions=["testing"])
    assert list(reg.planes) == ["testing.plain", "testing.jobs"]
    assert list(reg.cells) == ["testing.text", "testing.program"]
    assert list(reg.contents) == ["testing.Note", "testing.Plain"]


# --- Layout ------------------------------------------------------------------------


def _mark(root: Path) -> None:
    """``root`` made a space as far as finding one goes: its Space store file."""
    file = data_dir(root) / host.SPACE_STORE.file
    file.parent.mkdir(parents=True)
    file.touch()


def test_a_space_is_found_by_its_space_store_up_from_here(tmp_path):
    root = tmp_path / "space"
    nested = root / "a" / "b"
    nested.mkdir(parents=True)
    assert not is_space(root)
    assert find_space(nested) is None
    # A data dir alone (the user's ~/.nuspace config) is no space.
    (root / DATA_DIR).mkdir()
    assert find_space(nested) is None
    _mark(root)
    assert is_space(root)
    assert find_space(nested) == root.resolve()


@pytest.mark.parametrize("old", ["CURRENT", "kernel.sqlite", f"{DATA_DIR}/kernel.sqlite"])
def test_an_older_space_is_told_apart(tmp_path, old):
    (tmp_path / old).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / old).touch()
    assert is_older(tmp_path)
    with pytest.raises(Refused, match="older nuspace store format"):
        DataDir(str(tmp_path), [host.SPACE_STORE.file]).setup(None)
    assert not (data_dir(tmp_path) / "store").exists()
    _mark(tmp_path)
    assert not is_older(tmp_path)


def test_the_data_dir_holds_a_folder_per_store(tmp_path):
    files = [s.file for s in (*host.CORE, WEB_STORE, CONN_STORE)]
    DataDir(str(tmp_path), files).setup(None)
    assert (data_dir(tmp_path) / "store").is_dir()
    assert (data_dir(tmp_path) / "devices" / "web").is_dir()


def test_fresh_deletes_a_store_file_and_what_sqlite_keeps_beside_it(tmp_path):
    db = tmp_path / "conn.db"
    for f in (db, tmp_path / "conn.db-wal", tmp_path / "conn.db-shm", tmp_path / "keep.db"):
        f.write_text("x")
    Fresh([str(db), str(tmp_path / "never.db")]).setup(None)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["keep.db"]


# --- The host lock -----------------------------------------------------------------


def test_the_lock_names_its_holder_and_refuses_a_second_open(tmp_path):
    path = str(tmp_path / LOCK_FILE)
    first = HostLock(path)
    first.setup(None)
    try:
        name, pid, _ = holder(path).split()
        assert (name, int(pid)) == (socket.gethostname(), os.getpid())
        with pytest.raises(Refused, match="open already in this process"):
            HostLock(path).setup(None)
    finally:
        first.cleanup()
    again = HostLock(path)
    again.setup(None)
    again.cleanup()


def test_a_lock_another_process_holds_refuses_the_open(tmp_path):
    path = str(tmp_path / LOCK_FILE)
    code = (
        "import sys, time\n"
        "from nuspace.host.lock import HostLock\n"
        f"HostLock({path!r}).setup(None)\n"
        "print('held', flush=True)\n"
        "time.sleep(60)\n"
    )
    other = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)  # noqa: S603
    try:
        assert other.stdout.readline().strip() == "held"
        with pytest.raises(
            Refused, match=f"open on {socket.gethostname()}, pid {other.pid}. Close it there"
        ):
            HostLock(path).setup(None)
    finally:
        other.kill()
        other.wait()
    # Its holder died: the lock went with it.
    mine = HostLock(path)
    mine.setup(None)
    mine.cleanup()


def test_a_lock_the_file_system_cannot_take_opens_with_a_warning(tmp_path, monkeypatch):
    def nolock(fd, cmd):
        raise OSError(errno.ENOLCK, "No locks available")

    monkeypatch.setattr(lock_module.fcntl, "lockf", nolock)
    path = str(tmp_path / LOCK_FILE)
    lock = HostLock(path)
    with pytest.warns(LockWarning, match="opening without it"):
        lock.setup(None)
    assert not holder(path)
    lock.cleanup()


def test_a_throwaway_root_is_made_at_setup_and_removed_with_its_data_at_cleanup(tmp_path):
    root = tmp_path / "tmp-space"
    throwaway = Throwaway(str(root))
    throwaway.setup(None)
    assert root.is_dir()
    (data_dir(root) / "store").mkdir(parents=True)
    (data_dir(root) / "store" / "space.db").write_text("x")
    throwaway.cleanup()
    assert not root.exists()


# --- make_space -------------------------------------------------------------------------


_EVERY_STORE = (*host.CORE, WEB_STORE, CONN_STORE)


async def _aread(root: Path, term: nu.Nu, stores=_EVERY_STORE) -> object:
    """``term`` read from the space at ``root``, its stores opened plain, beside any host."""
    data = data_dir(root)
    navs = [nustd.kv.sqlite_navigator(str(data / s.file), tags=(s.root,)) for s in stores]
    value, _ = await nu.arun(nu.With(*navs, body=nuspace.atomic(term)))
    return value


def _read(root: Path, term: nu.Nu, stores=_EVERY_STORE) -> object:
    """``term`` read from the space at ``root``, its stores opened plain."""
    return asyncio.run(_aread(root, term, stores))


async def _apoll(root: Path, term: nu.Nu, pred, stores=_EVERY_STORE, timeout: float = 30.0):
    """``term`` read from ``root`` until ``pred`` holds of it, while a host runs the space."""
    deadline = time.monotonic() + timeout
    while True:
        with contextlib.suppress(Exception):  # the host may not have made the stores yet
            value = await _aread(root, term, stores)
            if pred(value):
                return value
        if time.monotonic() > deadline:
            msg = f"timed out polling {root}"
            raise AssertionError(msg)
        await asyncio.sleep(0.2)


def _write(root: Path, store, term: nu.Nu) -> None:
    file = str(data_dir(root) / store.file)
    navs = nustd.kv.sqlite_navigator(file, tags=(store.root,))
    asyncio.run(nu.arun(nu.With(navs, body=nuspace.atomic(term))))


def _make(root: Path, **kwargs) -> None:
    nu.eval_in_loop(nu.compile(host.make_space(root, **kwargs)), nu.Context())


def test_make_space_seeds_a_fresh_space_and_keeps_an_existing_one(tmp_path):
    root = tmp_path / "space"
    _make(root)
    assert is_space(root)
    info = _read(root, Space.info.extract())
    assert info["format"] == FORMAT
    planes = set(_read(root, nu.list(Space.planes.keys())))
    assert {"root", init.PLANE, _read(root, Web.roles["home"])} <= planes
    assert set(_read(root, nu.list(init.boot_list().keys()))) == set(init.BOOTED)
    # A second make keeps what is there: a booted plane stays booted.
    _write(root, host.STATE_STORE, init.boot_list().set_item("mine", True))
    _make(root)
    assert "mine" in _read(root, nu.list(init.boot_list().keys()))
    assert _read(root, Space.info.created_at) == info["created_at"]


def test_headless_opens_every_device_store_and_seeds_no_device_plane(tmp_path):
    root = tmp_path / "space"
    _make(root, devices=())
    assert is_space(root)
    assert (data_dir(root) / WEB_STORE.file).exists()
    assert (data_dir(root) / CONN_STORE.file).exists()
    assert _read(root, Web.roles.extract()) == {}
    assert _read(root, nu.list(Web.planes.keys())) == []
    # conn.db is made fresh at a headless open too.
    _write(root, CONN_STORE, Conn.connections["tab"].order.set(["p"]))
    _make(root, devices=())
    assert _read(root, Conn.connections.extract()) == {}


def test_conn_is_made_fresh_at_every_open_web_is_kept(tmp_path):
    root = tmp_path / "space"
    _make(root)
    _write(root, CONN_STORE, Conn.connections["tab"].order.set(["p"]))
    home = _read(root, Web.roles["home"])
    _write(root, WEB_STORE, nuspace.web.Web.recents.set([home]))
    _make(root)
    assert _read(root, Conn.connections.extract()) == {}
    assert _read(root, nuspace.web.Web.recents.extract()) == [home]
    assert _read(root, Web.roles["home"]) == home


def test_a_space_of_another_format_is_refused_before_anything_is_written(tmp_path):
    root = tmp_path / "space"
    _make(root)
    _write(root, host.SPACE_STORE, Space.info.format.set(FORMAT + 1))
    _write(root, CONN_STORE, Conn.connections["tab"].order.set(["p"]))
    with pytest.raises(Refused, match="another store format"):
        _make(root)
    # conn.db is recreated after the format check: the refused open left it.
    assert _read(root, Conn.connections["tab"].order.extract()) == ["p"]
    # The lock went with the refused open.
    assert holder(str(data_dir(root) / LOCK_FILE))
    _write(root, host.SPACE_STORE, Space.info.format.set(FORMAT))
    _make(root)


def test_an_unknown_device_is_refused_at_build(tmp_path):
    with pytest.raises(Missing, match="no device 'tv'"):
        host.open_space(tmp_path, devices=("tv",))


# --- open_space, for real ---------------------------------------------------------------


async def _opened(root: Path, **kwargs):
    """``host.headless`` on this loop, held open: ``(ctx, done, task)``. Close with ``done.set()``."""
    loop = asyncio.get_running_loop()
    ready, done = loop.create_future(), asyncio.Event()
    hold = nu.With(MADE_STORE, body=nu.let(_Hold(ready, done), lambda _: nu.Noop()))
    term = host.headless(root, spares=0, name="nuspace-host", extensions=(), body=hold, **kwargs)
    task = asyncio.create_task(nu.arun(term))
    waiting = asyncio.ensure_future(asyncio.shield(ready))
    finished, _ = await asyncio.wait({waiting, task}, timeout=30, return_when="FIRST_COMPLETED")
    if task in finished:
        task.result()
    return await waiting, done, task


async def _until(ctx, term, pred, timeout: float = 20.0):
    deadline = time.monotonic() + timeout
    while True:
        value, _ = await nu.arun(nuspace.atomic(term), ctx)
        if pred(value):
            return value
        if time.monotonic() > deadline:
            msg = f"timed out, last read: {value!r}"
            raise AssertionError(msg)
        await asyncio.sleep(0.1)


async def _ended(ctx, runs: list[str]) -> tuple[dict, dict, dict]:
    """The rows of ``runs``, of their cell runs, and of their workers, read in ``ctx``."""
    rows = Space.exec
    plane_runs, _ = await nu.arun(nuspace.atomic(rows.plane_runs.extract()), ctx)
    cell_runs, _ = await nu.arun(nuspace.atomic(rows.cell_runs.extract()), ctx)
    workers, _ = await nu.arun(nuspace.atomic(rows.workers.extract()), ctx)
    return (
        {r: plane_runs[r] for r in runs},
        {c: row for c, row in cell_runs.items() if row["plane_run"] in runs},
        {w: row for w, row in workers.items() if row["plane_run"] in runs},
    )


async def test_a_clean_close_ends_what_is_live_so_the_reopen_reaps_nothing(tmp_path, capfd):
    root = tmp_path / "space"
    before = time.time()
    ctx, done, task = await _opened(root)
    try:
        live = Space.exec.indexes.live
        info, _ = await nu.arun(nuspace.atomic(Space.info.extract()), ctx)
        assert info["path"] == str(root.resolve())
        assert info["opened_at"] >= before
        runs = await _until(ctx, nu.list(live.plane_runs.keys()), lambda rs: len(rs) == 4)
        planes = {
            (await nu.arun(nuspace.atomic(Space.exec.plane_runs[r].plane), ctx))[0] for r in runs
        }
        assert planes == {init.PLANE, *init.BOOTED}
        with pytest.raises(Refused, match="open already in this process"):
            await nu.arun(host.headless(root))
    finally:
        done.set()
        await asyncio.wait_for(task, 15)
    capfd.readouterr()
    # The close ended every run, cell run and worker interrupted; the reopen's reap finds none.
    ctx, done, task = await _opened(root)
    try:
        assert "nuspace reap" not in capfd.readouterr().err
        plane_runs, cell_runs, workers = await _ended(ctx, runs)
        assert {(r["exit"], r["error"]) for r in plane_runs.values()} == {
            (EXIT_INTERRUPTED, CLOSED)
        }
        assert cell_runs
        assert {(c["exit"], c["error"]) for c in cell_runs.values()} == {(EXIT_INTERRUPTED, CLOSED)}
        # Every worker ended by the close, a per cell run one (init's, on mp) too.
        assert workers
        assert {(w["exit"], w["error"]) for w in workers.values()} == {(EXIT_INTERRUPTED, CLOSED)}
        fresh = await _until(ctx, nu.list(live.plane_runs.keys()), lambda rs: len(rs) == 4)
        assert set(fresh).isdisjoint(runs)
    finally:
        done.set()
        await asyncio.wait_for(task, 15)


def test_served_open_compiles_and_validates(tmp_path):
    term = host.serve(tmp_path, extensions=["testing"], open_browser=False, static=None, port=0)
    nu.validate(nu.compile(term))


# --- with_plane -------------------------------------------------------------------------


_COUNTER = PlaneSpec("nudemos.counter", "Counter", cells=(("count", "1"),), backend="async")


async def test_with_plane_reuses_the_newest_plane_of_its_spec_or_makes_one(store):
    await store.run(presets._plane_of(_COUNTER, MADE))
    first = await store.run(MADE)
    assert first.startswith("p_")
    await store.run(presets._plane_of(_COUNTER, MADE))
    assert await store.run(MADE) == first
    await store.run(nuspace.atomic(nuspace.plane.remove(first)))
    await store.run(presets._plane_of(_COUNTER, MADE))
    second = await store.run(MADE)
    assert second not in ("", first)
    ids = Space.indexes.spec_planes[registered_name(_COUNTER)].ids
    assert await store.read(nu.list(ids.keys())) == [first, second]


async def test_with_plane_headless_lands_the_web_row_of_a_spec_that_shows_on_the_web(tmp_path):
    """No web driver runs, but the web device's stores are open: add_plane writes the web row."""
    root = tmp_path / "space"
    spec = PlaneSpec(
        "nudemos.board",
        "Board",
        cells=(("count", "1"),),
        backend="async",
        web=WebOptions(compact=True),
    )
    term = presets.with_plane(root, spec, web=False, spares=0, name="nuspace-host", extensions=())
    task = asyncio.create_task(nu.arun(term))
    try:
        planes = await _apoll(root, nu.list(Web.planes.keys()), bool)
        assert len(planes) == 1
        assert await _aread(root, Space.planes[planes[0]].spec) == registered_name(spec)
        assert await _aread(root, Web.planes[planes[0]].compact) is True
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.wait_for(task, 15)


@pytest.mark.parametrize(("web", "open_browser"), [(True, True), (True, False), (False, False)])
def test_with_plane_compiles(monkeypatch, web, open_browser):
    _points(monkeypatch, [])
    term = presets.with_plane(None, _COUNTER, web=web, open_browser=open_browser, static=None)
    nu.validate(nu.compile(term))


def test_with_plane_by_an_unknown_name_is_missing():
    with pytest.raises(Missing):
        presets.with_plane(None, "nobody.nothing")


# --- Browse ----------------------------------------------------------------------------


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


async def test_browse_opens_once_the_port_answers(monkeypatch):
    opened: list[str] = []
    monkeypatch.setattr(interactions.webbrowser, "open", opened.append)
    server = await asyncio.start_server(lambda r, w: w.close(), "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        url = f"http://127.0.0.1:{port}/p_x"
        await interactions.browse(url, "0.0.0.0", port)  # noqa: S104
    finally:
        server.close()
        await server.wait_closed()
    assert opened == [url]


async def test_browse_gives_up_quietly(monkeypatch):
    opened: list[str] = []
    monkeypatch.setattr(interactions.webbrowser, "open", opened.append)
    await interactions.browse("http://x", "127.0.0.1", _free_port(), timeout=0.2)
    assert opened == []


async def test_browse_as_a_term_reads_its_url_at_run_time(monkeypatch):
    opened: list[str] = []
    monkeypatch.setattr(interactions.webbrowser, "open", opened.append)
    server = await asyncio.start_server(lambda r, w: w.close(), "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    base = f"http://127.0.0.1:{port}/"
    term = nu.let("p_x", lambda plane: interactions.Browse(nu.Str(base) + nu.Str(plane), "", port))
    try:
        await nu.arun(term)
    finally:
        server.close()
        await server.wait_closed()
    assert opened == [base + "p_x"]


# --- nuspace run and Ctrl+C ----------------------------------------------------------------


def _left(pid: int, data: Path) -> list[str]:
    """Processes still up from the run: in its session, or naming its data dir or socket."""
    out = subprocess.run(["ps", "-eo", "pid,sid,args"], capture_output=True, text=True).stdout  # noqa: S607
    rows = [line.split(None, 2) for line in out.splitlines()[1:]]
    return [r[2] for r in rows if len(r) == 3 and (r[1] == str(pid) or str(data) in r[2])]


def _nuspace_run(root: Path) -> subprocess.Popen:
    """``nuspace run --headless`` on ``root``, in a session of its own."""
    env = dict(os.environ, NUSPACE_TELEMETRY="0")
    return subprocess.Popen(  # noqa: S603
        [sys.executable, "-m", "nuspace._cli", "run", "--headless", str(root)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        env=env,
    )


def _live_runs(root: Path, n: int = 4) -> list[str]:
    """The live plane runs of the space a host runs, once there are ``n`` (init and its boots)."""
    live = Space.exec.indexes.live.plane_runs
    term = nu.list(live.keys())
    return asyncio.run(_apoll(root, term, lambda rs: len(rs) == n, stores=host.CORE))


def test_nuspace_run_stops_on_ctrl_c_ends_what_is_live_and_leaves_no_process(tmp_path):
    root = tmp_path / "space"
    run = _nuspace_run(root)
    try:
        runs = _live_runs(root)
        assert _left(run.pid, data_dir(root)), "the space never came up"
        run.send_signal(signal.SIGINT)
        out, _ = run.communicate(timeout=20)
    finally:
        if run.poll() is None:
            os.killpg(run.pid, signal.SIGKILL)
            run.wait()
    assert run.returncode == 0, out.decode()
    assert "Stopped" in out.decode()
    assert "nuspace close" not in out.decode()
    time.sleep(0.5)
    assert _left(run.pid, data_dir(root)) == []
    # The cancelled kernel arms and the close did not end anything twice.
    rows = _read(root, Space.exec.plane_runs.extract(), stores=host.CORE)
    assert {(rows[r]["exit"], rows[r]["error"]) for r in runs} == {(EXIT_INTERRUPTED, CLOSED)}
    live = _read(root, Space.exec.indexes.live.extract(), stores=host.CORE)
    assert live["plane_runs"] == {} and live["workers"] == {}


async def test_a_host_killed_mid_run_is_reaped_killed_at_the_next_open(tmp_path, capfd):
    """SIGKILL, as a crash: no close runs, so the reopen's reap ends what was live, killed."""
    root = tmp_path / "space"
    run = _nuspace_run(root)
    try:
        live = Space.exec.indexes.live.plane_runs
        term = nu.list(live.keys())
        runs = await _apoll(root, term, lambda rs: len(rs) == 4, stores=host.CORE)
    finally:
        os.killpg(run.pid, signal.SIGKILL)
        run.wait()
    capfd.readouterr()
    ctx, done, task = await _opened(root)
    try:
        err = capfd.readouterr().err
        for r in runs:
            assert f"nuspace reap: plane run {r} of plane " in err
        plane_runs, cell_runs, _ = await _ended(ctx, runs)
        assert {(r["exit"], r["error"]) for r in plane_runs.values()} == {(EXIT_KILLED, LEFT_OVER)}
        assert {c["exit"] for c in cell_runs.values()} <= {EXIT_KILLED}
    finally:
        done.set()
        await asyncio.wait_for(task, 15)


# --- Imports ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("imported", "absent"),
    [
        ("nuspace", ("starlette", "uvicorn", "click", "nustd.ws_server", "nuspace._telemetry")),
        ("nuspace.host", ("starlette", "uvicorn", "click", "nustd.ws_server")),
    ],
)
def test_importing_nuspace_or_the_host_pulls_in_no_server_and_no_cli(imported, absent):
    code = f"import sys, {imported}\nprint(sorted(m for m in {absent!r} if m in sys.modules))"
    out = subprocess.run(  # noqa: S603 -- our own interpreter, a fixed script
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert out.stdout.strip() == "[]"
