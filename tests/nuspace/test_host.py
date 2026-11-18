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
import logging
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
from nuspace.errors import Missing, Refused
from nuspace.kernel import CLOSED, LEFT_OVER, Env
from nuspace.shapes import EXIT_INTERRUPTED, EXIT_KILLED, FORMAT, Space, stores
from nuspace.space import local
from nuspace.space.blocks import browse
from nuspace.space.blocks import lock as lock_module
from nuspace.space.blocks.lock import Lock, LockWarning, holder
from nuspace.space.blocks.logs import Logged
from nuspace.space.blocks.meta import (
    DATA_DIR,
    META_FILE,
    Meta,
    data_dir,
    find_space,
    is_space,
    read_meta,
    stamp,
    write_meta,
)
from nuspace.space.blocks.notifier import Notifier, holders
from nuspace.space.blocks.resources import DataDir, Throwaway
from nuspace.space.local import presets
from nuspace.space.local._disk import Marked
from nuspace.space.local.layout import DIRS, KERNEL_LOCK, is_older, made_before
from nuspace.space.local.layout import STORES as PLACES
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
from nustd.valkey.resources import ping, socket_path_for


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


def test_the_assembly_env_wins_over_an_installed_one(monkeypatch):
    installed = Extension(
        (_plane("plain", "Installed"), _plane("jobs")), (), (), {"db": _env("installed")}
    )
    _points(monkeypatch, [_Point("installed", lambda: installed)])
    with pytest.warns(RegistryWarning) as caught:
        reg = space_registry(envs={"db": _env("mine")})
    assert {str(w.message) for w in caught} == {
        "Env 'db' from installed ignored: the assembly registered it first",
    }
    assert list(reg.planes) == ["installed.plain", "installed.jobs"]
    assert reg.envs["db"]().label == "mine"


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
    assert list(reg.cells) == ["testing.text", "testing.program", "testing.tail", "testing.snap"]
    assert list(reg.contents) == ["testing.Note", "testing.Plain"]


# --- Layout ------------------------------------------------------------------------


def _mark(root: Path) -> None:
    """``root`` made a space as far as finding one goes: its ``meta.json``."""
    write_meta(root, Meta("local", "2026-11-18T00:00:00+00:00"))


def _made_before(root: Path) -> None:
    """``root`` made a space as one was before ``meta.json``: its Space store file alone."""
    file = data_dir(root) / PLACES[Space].file
    file.parent.mkdir(parents=True)
    file.touch()


def test_a_space_is_found_by_its_meta_up_from_here(tmp_path):
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
        Marked(str(tmp_path)).setup(None)
    assert not (data_dir(tmp_path) / META_FILE).exists()
    _mark(tmp_path)
    assert not is_older(tmp_path)


def test_the_data_dir_holds_a_folder_per_store(tmp_path):
    DataDir(str(tmp_path), DIRS).setup(None)
    for root in PLACES:
        assert (data_dir(tmp_path) / PLACES[root].file).parent.is_dir()


def test_meta_names_the_assembly_and_another_assembly_is_refused(tmp_path):
    made = stamp(tmp_path, "local")
    assert read_meta(tmp_path) == made
    assert made.assembly == "local"
    assert stamp(tmp_path, "local") == made
    with pytest.raises(Refused, match="space of the 'local' assembly, not 'shard'"):
        stamp(tmp_path, "shard")
    (data_dir(tmp_path) / META_FILE).write_text("{oops")
    with pytest.raises(Refused, match="does not read as a space's meta"):
        read_meta(tmp_path)


def test_a_space_made_before_meta_is_found_and_adopted_and_its_host_lock_ignored(tmp_path):
    root = tmp_path / "space"
    _made_before(root)
    (data_dir(root) / "host.lock").write_text(f"{socket.gethostname()} 1 0\n")
    assert made_before(root)
    assert not is_space(root)
    assert not is_older(root)
    Marked(str(root)).setup(None)
    assert read_meta(root).assembly == "local"
    assert is_space(root)
    assert not made_before(root)


# --- The lock ----------------------------------------------------------------------


def test_the_lock_names_its_holder_and_refuses_a_second_take(tmp_path):
    path = str(tmp_path / "kernel.lock")
    first = Lock(path, "kernel")
    first.setup(None)
    try:
        name, pid, _ = holder(path).split()
        assert (name, int(pid)) == (socket.gethostname(), os.getpid())
        with pytest.raises(Refused, match="the kernel of this space runs in this process already"):
            Lock(path, "kernel").setup(None)
    finally:
        first.cleanup()
    again = Lock(path, "kernel")
    again.setup(None)
    again.cleanup()


def test_a_lock_another_process_holds_refuses_the_open(tmp_path):
    path = str(tmp_path / "kernel.lock")
    code = (
        "import sys, time\n"
        "from nuspace.space.blocks.lock import Lock\n"
        f"Lock({path!r}, 'kernel').setup(None)\n"
        "print('held', flush=True)\n"
        "time.sleep(60)\n"
    )
    other = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)  # noqa: S603
    try:
        assert other.stdout.readline().strip() == "held"
        told = f"the kernel of this space runs on {socket.gethostname()}, pid {other.pid}. Stop it"
        with pytest.raises(Refused, match=told):
            Lock(path, "kernel").setup(None)
    finally:
        other.kill()
        other.wait()
    # Its holder died: the lock went with it.
    mine = Lock(path, "kernel")
    mine.setup(None)
    mine.cleanup()


def test_a_lock_the_file_system_cannot_take_opens_with_a_warning(tmp_path, monkeypatch):
    def nolock(fd, cmd):
        raise OSError(errno.ENOLCK, "No locks available")

    monkeypatch.setattr(lock_module.fcntl, "lockf", nolock)
    path = str(tmp_path / "kernel.lock")
    lock = Lock(path, "web")
    with pytest.warns(LockWarning, match="going on without it"):
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


_EVERY_STORE = (*stores.CORE, WEB_STORE, CONN_STORE)


async def _aread(root: Path, term: nu.Nu, stores=_EVERY_STORE) -> object:
    """``term`` read from the space at ``root``, its stores opened plain, beside any host."""
    data = data_dir(root)
    navs = [
        nustd.kv.sqlite_navigator(str(data / PLACES[s.root].file), tags=(s.root,)) for s in stores
    ]
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


async def _awrite(root: Path, store, term: nu.Nu) -> None:
    file = str(data_dir(root) / PLACES[store.root].file)
    navs = nustd.kv.sqlite_navigator(file, tags=(store.root,))
    await nu.arun(nu.With(navs, body=nuspace.atomic(term)))


def _write(root: Path, store, term: nu.Nu) -> None:
    asyncio.run(_awrite(root, store, term))


def _make(root: Path, **kwargs) -> None:
    nu.eval_in_loop(nu.compile(local.make_space(root, **kwargs)), nu.Context())


def test_make_space_seeds_a_fresh_space_and_keeps_an_existing_one(tmp_path):
    root = tmp_path / "space"
    _make(root)
    assert is_space(root)
    info = _read(root, Space.info.extract())
    assert info["format"] == FORMAT
    planes = set(_read(root, nu.list(Space.planes.keys())))
    keyed = {key: _read(root, nuspace.plane.keyed(key)) for key in (init.KEY, *init.BOOTED)}
    assert {"root", keyed[init.KEY], _read(root, Web.roles["home"])} <= planes
    booted = {keyed[key] for key in init.BOOTED}
    assert set(_read(root, nu.list(init.boot_list().keys()))) == booted
    # A second make keeps what is there: a booted plane stays booted.
    booting = nuspace.at.plane(id=keyed[init.KEY]).state(init.Boot).planes
    _write(root, stores.STATE_STORE, booting.set_item("mine", True))
    _make(root)
    assert "mine" in _read(root, nu.list(init.boot_list().keys()))
    assert _read(root, Space.info.created_at) == info["created_at"]


def test_a_space_made_before_meta_opens_with_its_data_and_gets_its_meta(tmp_path):
    root = tmp_path / "space"
    _make(root)
    created = _read(root, Space.info.created_at)
    (data_dir(root) / META_FILE).unlink()
    (data_dir(root) / "host.lock").write_text("elsewhere 1 0\n")
    assert made_before(root)
    _make(root)
    assert read_meta(root).assembly == "local"
    assert _read(root, Space.info.created_at) == created


def test_make_space_makes_every_store_and_leaves_conn_and_web_as_they_are(tmp_path):
    root = tmp_path / "space"
    _make(root)
    assert (data_dir(root) / PLACES[Web].file).exists()
    assert (data_dir(root) / PLACES[Conn].file).exists()
    _write(root, CONN_STORE, Conn.connections["tab"].order.set(["p"]))
    home = _read(root, Web.roles["home"])
    _write(root, WEB_STORE, nuspace.web.Web.recents.set([home]))
    _make(root)
    # Conn is web's driver's to clear, when web starts: making a space runs no driver.
    assert _read(root, Conn.connections["tab"].order.extract()) == ["p"]
    assert _read(root, nuspace.web.Web.recents.extract()) == [home]
    assert _read(root, Web.roles["home"]) == home


def test_a_space_of_another_format_is_refused_before_anything_is_written(tmp_path):
    root = tmp_path / "space"
    _make(root)
    _write(root, stores.SPACE_STORE, Space.info.format.set(FORMAT + 1))
    _write(root, CONN_STORE, Conn.connections["tab"].order.set(["p"]))
    with pytest.raises(Refused, match="another store format"):
        _make(root)
    # conn.db is recreated after the format check: the refused open left it.
    assert _read(root, Conn.connections["tab"].order.extract()) == ["p"]
    # The lock went with the refused open.
    assert holder(str(data_dir(root) / KERNEL_LOCK))
    _write(root, stores.SPACE_STORE, Space.info.format.set(FORMAT))
    _make(root)


# --- open_space, for real ---------------------------------------------------------------


async def _opened(root: Path, **kwargs):
    """``local.headless`` on this loop, held open: ``(ctx, done, task)``. Close with ``done.set()``."""
    loop = asyncio.get_running_loop()
    ready, done = loop.create_future(), asyncio.Event()
    hold = nu.With(MADE_STORE, body=nu.let(_Hold(ready, done), lambda _: nu.Noop()))
    term = local.headless(root, spares=0, name="nuspace-host", extensions=(), body=hold, **kwargs)
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
        # Close ends only what was started: an ask still pending is the next kernel's to start.
        up = nu.List.of(*(Space.exec.plane_runs[r].started_at.exists() for r in runs))
        await _until(ctx, up, all)
        planes = {
            (await nu.arun(nuspace.atomic(Space.exec.plane_runs[r].plane), ctx))[0] for r in runs
        }
        keyed = [nuspace.plane.keyed(key) for key in (init.KEY, *init.BOOTED)]
        ids = {(await nu.arun(nuspace.atomic(k), ctx))[0] for k in keyed}
        assert planes == ids
        with pytest.raises(Refused, match="the kernel of this space runs in this process already"):
            await nu.arun(local.headless(root))
    finally:
        done.set()
        await asyncio.wait_for(task, 15)
    capfd.readouterr()
    # The close ended every started run, its cell runs and workers interrupted; reap finds none.
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
    term = local.serve(tmp_path, extensions=["testing"], open_browser=False, static=None, port=0)
    nu.validate(nu.compile(term))


#: A process holding a store's file open, as a worker does, until its stdin closes.
_HOLDER = """
import sqlite3, sys
db = sqlite3.connect(sys.argv[1])
db.execute("select count(*) from sqlite_master").fetchall()
print("held", flush=True)
sys.stdin.read()
"""


async def test_web_clears_conn_by_a_commit_while_a_worker_holds_its_file(tmp_path):
    """W2 and W7: at web's start Conn is emptied in place, and the runs nav asked for are stopped."""
    root = tmp_path / "space"
    await nu.arun(local.make_space(root))
    conn = data_dir(root) / PLACES[Conn].file
    await _awrite(root, CONN_STORE, Conn.connections["old-tab"].order.set(["p"]))

    def asked(run: nu.ObjectRef) -> nu.Nu:
        made = nuspace.plane.add("p1", backend="async")
        return made >> nuspace.plane_run.add("p1", by="nav", into=run)

    await _awrite(root, stores.SPACE_STORE, nu.let("", asked))
    holder = subprocess.Popen(  # noqa: S603
        [sys.executable, "-c", _HOLDER, str(conn)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout.readline().strip() == "held"
        inode = conn.stat().st_ino
        loop = asyncio.get_running_loop()
        ready, done = loop.create_future(), asyncio.Event()
        hold = nu.With(MADE_STORE, body=nu.let(_Hold(ready, done), lambda _: nu.Noop()))
        term = local.serve(
            root,
            port=_free_port(),
            open_browser=False,
            static=None,
            spares=0,
            extensions=(),
            body=hold,
        )
        task = asyncio.create_task(nu.arun(term))
        try:
            waiting = asyncio.ensure_future(asyncio.shield(ready))
            finished, _ = await asyncio.wait(
                {waiting, task}, timeout=30, return_when="FIRST_COMPLETED"
            )
            if task in finished:
                task.result()
            ctx = await waiting
            await _until(ctx, Conn.connections.extract(), lambda tabs: tabs == {})
            runs = Space.exec.plane_runs.extract()
            rows = await _until(
                ctx,
                runs,
                lambda rs: all(r.get("interrupt_at") for r in rs.values() if r.get("by") == "nav"),
            )
            assert [r for r in rows.values() if r.get("by") == "nav"]
        finally:
            done.set()
            await asyncio.wait_for(task, 15)
        # The same file, never deleted under the process holding it.
        assert conn.stat().st_ino == inode
        assert holder.poll() is None
    finally:
        holder.communicate("")


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
        web=WebOptions(width="board"),
    )
    term = presets.with_plane(root, spec, web=False, spares=0, name="nuspace-host", extensions=())
    task = asyncio.create_task(nu.arun(term))
    try:
        planes = await _apoll(root, nu.list(Web.planes.keys()), bool)
        assert len(planes) == 1
        assert await _aread(root, Space.planes[planes[0]].spec) == registered_name(spec)
        assert await _aread(root, Web.planes[planes[0]].width) == "board"
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


# --- The notifier ---------------------------------------------------------------------


def _answers(path: Path) -> bool:
    return ping(socket_path_for(path), 0.2)


def test_a_joiner_keeps_the_server_when_its_owner_leaves_and_the_last_out_stops_it(tmp_path):
    path = tmp_path / "valkey"
    owner, joiner = Notifier(str(path)), Notifier(str(path))
    owner.setup(None)
    try:
        joiner.setup(None)
        assert owner.owned
        assert not joiner.owned
        assert len(holders(path)) == 2
        owner.cleanup()
        assert _answers(path), "the owner left first and took the server along"
        assert len(holders(path)) == 1
    finally:
        owner.cleanup()
        joiner.cleanup()
    assert not _answers(path)
    assert holders(path) == []


#: A process owning or joining the notifier at argv[1], saying which, until its stdin closes.
_NOTIFIED = """
import sys
from nuspace.space.blocks.notifier import Notifier
n = Notifier(sys.argv[1])
n.setup(None)
print("owned" if n.owned else "joined", flush=True)
sys.stdin.read()
n.cleanup()
"""


def _notified(path: Path) -> subprocess.Popen:
    return subprocess.Popen(  # noqa: S603
        [sys.executable, "-c", _NOTIFIED, str(path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )


def test_processes_coming_up_together_start_one_server(tmp_path):
    path = tmp_path / "valkey"
    procs = [_notified(path) for _ in range(4)]
    try:
        said = sorted(p.stdout.readline().strip() for p in procs)
        assert said == ["joined", "joined", "joined", "owned"]
    finally:
        for p in procs:
            p.communicate("", timeout=20)
    assert not _answers(path)
    assert holders(path) == []


def test_a_holder_that_crashed_is_pruned_and_the_last_clean_exit_stops_the_server(tmp_path):
    path = tmp_path / "valkey"
    crashed = _notified(path)
    assert crashed.stdout.readline().strip() == "owned"
    mine = Notifier(str(path))
    mine.setup(None)
    try:
        crashed.kill()
        crashed.wait()
        # No watchdog: the server outlives its owner, for the holder left.
        assert _answers(path)
    finally:
        mine.cleanup()
    assert not _answers(path)
    assert holders(path) == []


# --- Logs ------------------------------------------------------------------------------


def test_the_log_block_points_logging_at_its_file_while_it_holds(tmp_path):
    path = tmp_path / "kernel" / "kernel.log"
    held = Logged(str(path), "kernel")
    held.setup(None)
    logging.getLogger("nuspace.test").info("from nuspace")
    logging.getLogger("somelib").info("not this")
    logging.getLogger("somelib").warning("but this")
    held.cleanup()
    logging.getLogger("nuspace.test").warning("after")
    said = path.read_text()
    assert f"kernel up on {socket.gethostname()}, pid {os.getpid()}" in said
    assert "from nuspace" in said
    assert "but this" in said
    assert "not this" not in said
    assert "kernel down" in said
    assert "after" not in said


# --- Browse ----------------------------------------------------------------------------


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


async def test_browse_opens_once_the_port_answers(monkeypatch):
    opened: list[str] = []
    monkeypatch.setattr(browse.webbrowser, "open", opened.append)
    server = await asyncio.start_server(lambda r, w: w.close(), "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        url = f"http://127.0.0.1:{port}/p_x"
        await browse.browse(url, "0.0.0.0", port)  # noqa: S104
    finally:
        server.close()
        await server.wait_closed()
    assert opened == [url]


async def test_browse_gives_up_quietly(monkeypatch):
    opened: list[str] = []
    monkeypatch.setattr(browse.webbrowser, "open", opened.append)
    await browse.browse("http://x", "127.0.0.1", _free_port(), timeout=0.2)
    assert opened == []


async def test_browse_as_a_term_reads_its_url_at_run_time(monkeypatch):
    opened: list[str] = []
    monkeypatch.setattr(browse.webbrowser, "open", opened.append)
    server = await asyncio.start_server(lambda r, w: w.close(), "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    base = f"http://127.0.0.1:{port}/"
    term = nu.let("p_x", lambda plane: browse.Browse(nu.Str(base) + nu.Str(plane), "", port))
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
    return asyncio.run(_apoll(root, term, lambda rs: len(rs) == n, stores=stores.CORE))


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
    rows = _read(root, Space.exec.plane_runs.extract(), stores=stores.CORE)
    assert {(rows[r]["exit"], rows[r]["error"]) for r in runs} == {(EXIT_INTERRUPTED, CLOSED)}
    live = _read(root, Space.exec.indexes.live.extract(), stores=stores.CORE)
    assert live["plane_runs"] == {} and live["workers"] == {}


async def test_a_host_killed_mid_run_is_reaped_killed_at_the_next_open(tmp_path, capfd):
    """SIGKILL, as a crash: no close runs, so the reopen's reap ends what was started, killed."""
    root = tmp_path / "space"
    run = _nuspace_run(root)
    try:
        live = Space.exec.indexes.live.plane_runs
        term = nu.list(live.keys())
        runs = await _apoll(root, term, lambda rs: len(rs) == 4, stores=stores.CORE)
        # Reap ends only what was started: an ask still pending is the next kernel's to start.
        up = nu.List.of(*(Space.exec.plane_runs[r].started_at.exists() for r in runs))
        await _apoll(root, up, all, stores=stores.CORE)
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
        ("nuspace.space", ("starlette", "uvicorn", "click", "nustd.ws_server")),
    ],
)
def test_importing_nuspace_or_the_host_pulls_in_no_server_and_no_cli(imported, absent):
    code = f"import sys, {imported}\nprint(sorted(m for m in {absent!r} if m in sys.modules))"
    out = subprocess.run(  # noqa: S603 -- our own interpreter, a fixed script
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert out.stdout.strip() == "[]"
