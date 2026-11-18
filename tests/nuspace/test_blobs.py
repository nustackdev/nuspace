"""The blob store and the upload area, wired into a space.

- the default store: plain files in the data dir;
- a cell's run, async or on a worker, puts into the store the host reads;
- a worker's run reads a file the tab posted, by path, through its session;
- a served space answers the blob routes and the upload intake, and wipes
  the upload area at open.
"""

from __future__ import annotations

import asyncio
import contextlib
import pickle
import socket
import time
from typing import TYPE_CHECKING

import httpx
import pytest
from _support.kernel import _Hold, ended, only_cell, opened, prog
from _support.made import MADE_STORE

import nu
import nuspace
import nustd.blob
import nustd.kv
from nu.lang import ScalarQuery
from nuspace.shapes import EXIT_OK
from nuspace.shapes.stores import CORE
from nuspace.space import local
from nuspace.space.blocks.meta import data_dir
from nuspace.space.blocks.workers import worker_context
from nuspace.space.local import binding
from nuspace.space.local.disk import Wiped
from nuspace.space.local.layout import BLOBS_DIR, UPLOADS_DIR
from nuspace.web.env import SessionWrap
from nuspace.web.session import SessionPipe, piped_session
from nustd.blob.backends import FilesBackend
from nustd.ui.core import WsSession
from nustd.ui.uploads import UploadView, tab_dir


if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from nu.lang.runtime import Runtime


pytestmark = pytest.mark.timeout(60)


def _backend(spec: nu.Provide) -> type:
    return nustd.blob.backend_of(spec).__class__


# --- the default store ------------------------------------------------------------------


def test_the_default_store_is_files_in_the_data_dir(tmp_path):
    spec = binding.blobs(tmp_path / ".nuspace")
    assert _backend(spec) is FilesBackend
    assert str(nustd.blob.backend_of(spec).root) == str(tmp_path / ".nuspace" / BLOBS_DIR)


def test_the_mount_serves_under_blobs():
    bid = "0123456789abcdef0123456789abcdef"
    assert nuspace.blobs.url(bid) == f"/blobs/{bid}"
    assert nuspace.Blobs.name == "blobs"


def test_the_worker_context_pickles_with_the_store(tmp_path):
    spec = nustd.blob.lmdb(nuspace.Blobs, tmp_path / "blobs")
    bindings = binding.stores(str(tmp_path), [s.root for s in CORE])
    pickle.loads(pickle.dumps(worker_context(bindings, spec)))  # noqa: S301 -- our own term


# --- a cell puts, the host reads --------------------------------------------------------


class Tick(nu.Shape):
    """The cell state the programs write, as ``_support.kernel``'s programs declare it."""

    n = nustd.kv.IntRef.slot()
    s = nustd.kv.StrRef.slot()


PUTS = prog(
    "put = nuspace.Blobs.put(b'from a cell', mime='text/plain', name='c.txt')",
    "return nu.let(put, lambda bid: nuspace.atomic(nuspace.here(Tick).s.set(bid)))",
)


@pytest.mark.parametrize("backend", ["async", "mp"])
async def test_a_cells_put_lands_in_the_store_the_host_reads(tmp_path, backend):
    data = tmp_path / ".nuspace"
    spec = nustd.blob.lmdb(nuspace.Blobs, data / BLOBS_DIR)
    k = await opened(data=str(data), blobs=spec)
    try:
        p, (c,) = await k.plane(PUTS, backend=backend)
        r = await k.start(p)
        row = await k.run_row(r, ended, 20.0)
        assert only_cell(row)["exit"] == EXIT_OK, only_cell(row)
        bid = await k.read(nuspace.at.cell(id=c).state(Tick).s)
        assert await k.run(nuspace.Blobs.get(bid)) == b"from a cell"
        meta = await k.run(nuspace.Blobs.meta(bid))
        assert (meta["mime"], meta["name"]) == ("text/plain", "c.txt")
    finally:
        await k.close()


# --- a worker reads what the tab posted -------------------------------------------------


class _Book:
    """The ws server's book with one live tab, ``s1``."""

    def __init__(self) -> None:
        self.tab = WsSession(ws=None)

    def session(self, sid: str) -> WsSession | None:
        return self.tab if sid == "s1" else None


class ReadUpload(ScalarQuery):
    """The bytes of upload ``token``, through the view the run has bound."""

    def __init__(self, token: str) -> None:
        super().__init__()
        self._payload = {"token": token}

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        def thunk(rt: Runtime) -> bytes:
            return rt.ctx.fabrics.get(UploadView).path(self._payload["token"]).read_bytes()

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        async def athunk(rt: Runtime) -> bytes:
            return rt.ctx.fabrics.get(UploadView).path(self._payload["token"]).read_bytes()

        return athunk


async def _in_thread(work: Callable[[], object]) -> object:
    """``work`` run on a fresh loop in another thread, as a worker runs."""
    return await asyncio.wait_for(asyncio.to_thread(lambda: asyncio.run(work())), timeout=10)


async def test_a_worker_reads_a_posted_file_by_path_through_its_session(tmp_path):
    root = tmp_path / "uploads"
    token = "ab" * 16
    tab_dir(root, "s1").mkdir(parents=True)
    (tab_dir(root, "s1") / token).write_bytes(b"picked in the tab")

    pipe = SessionPipe("127.0.0.1:0")
    pipe._web = _Book()
    pipe._server = await asyncio.start_server(pipe._serve, "127.0.0.1", 0)
    address = f"127.0.0.1:{pipe._server.sockets[0].getsockname()[1]}"
    try:

        async def work() -> object:
            body = piped_session(address, "s1", ReadUpload(token), uploads=str(root))
            value, _ = await nu.arun(body)
            return value

        assert await _in_thread(work) == b"picked in the tab"

        async def without() -> object:
            await nu.arun(piped_session(address, "s1", ReadUpload(token)))

        with pytest.raises(LookupError):
            await _in_thread(without)
    finally:
        await pipe.acleanup()


def test_the_session_wrap_carries_the_upload_root_and_pickles():
    wrap = pickle.loads(pickle.dumps(SessionWrap("127.0.0.1:9", "s1", "/tmp/up")))  # noqa: S301
    assert (wrap.address, wrap.sid, wrap.uploads) == ("127.0.0.1:9", "s1", "/tmp/up")


def test_wiped_removes_whole_dirs(tmp_path):
    gone = tmp_path / "area"
    (gone / "tab").mkdir(parents=True)
    (gone / "tab" / "f").write_bytes(b"x")
    Wiped([str(gone), str(tmp_path / "never")]).setup(None)
    assert not gone.exists()


# --- a served space ----------------------------------------------------------------------


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


async def _served(root: Path, port: int):
    """``local.web`` on this loop, held open: ``(done, task)``. Close with ``done.set()``."""
    await nu.arun(local.init(root))
    loop = asyncio.get_running_loop()
    ready, done = loop.create_future(), asyncio.Event()
    hold = nu.With(MADE_STORE, body=nu.let(_Hold(ready, done), lambda _: nu.Noop()))
    web = local.web(root, port=port, open_browser=False, static=None, extensions=(), body=hold)
    # Web runs only beside a kernel, the kernel on infra: all here, meeting through the files.
    term = local.infra(root, body=nu.Race(local.kernel(root, spares=0, extensions=()), web))
    task = asyncio.create_task(nu.arun(term))
    waiting = asyncio.ensure_future(asyncio.shield(ready))
    finished, _ = await asyncio.wait({waiting, task}, timeout=30, return_when="FIRST_COMPLETED")
    if task in finished:
        task.result()
    return done, task


async def _answering(base: str, client: httpx.AsyncClient, timeout: float = 20.0) -> None:
    deadline = time.monotonic() + timeout
    while True:
        with contextlib.suppress(httpx.TransportError):
            await client.get(f"{base}/blobs/{'0' * 32}")
            return
        assert time.monotonic() < deadline, "the server never came up"
        await asyncio.sleep(0.1)


async def test_a_served_space_serves_blobs_and_takes_uploads(tmp_path):
    root = tmp_path / "space"
    stale = data_dir(root) / UPLOADS_DIR / "old-tab"
    stale.mkdir(parents=True)
    port = _free_port()
    base = f"http://127.0.0.1:{port}"
    same = {"Sec-Fetch-Site": "same-origin"}
    done, task = await _served(root, port)
    try:
        async with httpx.AsyncClient() as client:
            await _answering(base, client)
            # The area is wiped at open: no tab of a past open is left.
            assert not stale.exists()
            assert (data_dir(root) / UPLOADS_DIR).is_dir()

            put = await client.post(
                f"{base}/blobs",
                content=b"0123456789",
                headers={**same, "Content-Type": "text/plain", "X-Blob-Name": "n.txt"},
            )
            assert put.status_code == 201, put.text
            bid = put.json()["id"]
            whole = await client.get(f"{base}{nuspace.blobs.url(bid)}")
            assert (whole.status_code, whole.content) == (200, b"0123456789")
            part = await client.get(f"{base}/blobs/{bid}", headers={"Range": "bytes=2-4"})
            assert (part.status_code, part.content) == (206, b"234")

            cross = await client.post(
                f"{base}/blobs", content=b"x", headers={"Sec-Fetch-Site": "cross-site"}
            )
            assert cross.status_code == 403
            # The intake is mounted: a tab that is not connected is refused, not missing.
            intake = await client.post(f"{base}/_nu/upload/nobody", content=b"x", headers=same)
            assert (intake.status_code, intake.text) == (403, "no live tab for this upload")
    finally:
        done.set()
        await asyncio.wait_for(task, 15)
    # The area goes with the server; the store stays.
    assert not (data_dir(root) / UPLOADS_DIR).exists()
    assert (data_dir(root) / BLOBS_DIR).is_dir()


def test_the_snap_cell_builds():
    from _support.specs import SNAP_SRC

    scope: dict = {}
    exec(compile(SNAP_SRC, "snap", "exec"), scope)  # noqa: S102 - a test cell's own source
    nu.validate(nu.compile(scope["out"]()))
