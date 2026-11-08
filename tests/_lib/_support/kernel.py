"""The kernel harness and programs shared by the kernel, system plane and host tests.

One kernel held open on the test's loop, headless, with real workers: the
Space and State stores on sqlite with a private notification server, reap,
then a worker pool whose workers open the same stores, the backends and the
kernel. Run ops against it, read the store, wait until the kernel has made
something true.

The stores are opened here, not through the host: the kernel needs only
them, the pool and :func:`nuspace.kernel.bound` around it.
"""

from __future__ import annotations

import asyncio
import multiprocessing
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import nu
import nuspace
import nustd.kv
import nustd.mp_pool
import nustd.valkey
from _support.made import MADE, MADE_STORE
from nu.lang import ScalarQuery
from nuspace import kernel
from nuspace.host.stores import SPACE_STORE, STATE_STORE
from nuspace.shapes import Space


if TYPE_CHECKING:
    from collections.abc import Callable


# --- Programs ------------------------------------------------------------------

_HEAD = """
import nu
import nustd.kv
import nuspace

class Tick(nu.Shape):
    n = nustd.kv.IntRef.slot()
    s = nustd.kv.StrRef.slot()

def out():
"""


def prog(*lines: str) -> str:
    """A program with ``Tick`` declared, whose ``out`` runs ``lines``."""
    return _HEAD + "".join(f"    {line}\n" for line in lines)


SET_42 = prog("return nuspace.atomic(nuspace.here(Tick).n.set(42))")
RAISES = prog('raise ValueError("boom")')
FOREVER = prog('print("built")', 'return nu.print("tick") >> nu.ForeverDo(nu.Delay(0.05))')
READS_TAG = prog(
    "from _support.kernel_envs import Tag",
    "return nuspace.atomic(nuspace.here(Tick).s.set(Tag.value))",
)
#: Holds its worker's loop, so it never hears an interrupt.
BLOCKS = prog(
    "from _support.actions import Block",
    "return nu.Delay(0.2) >> nu.let(Block(60), lambda _: nu.Noop())",
)
#: Takes its own worker process down, a moment in.
CRASHES = prog(
    "from _support.actions import Crash",
    "return nu.Delay(0.3) >> nu.let(Crash(3), lambda _: nu.Noop())",
)


# --- The stores -----------------------------------------------------------------

#: The core stores, as the kernel reads them.
STORES = (SPACE_STORE, STATE_STORE)

#: The notification server's dir inside a space's data dir.
VALKEY_DIR = "valkey"


def navigators(data: str) -> nu.With:
    """Every core store under ``data``, notified through its server, as any process opens them."""
    url = nustd.valkey.url_for(Path(data) / VALKEY_DIR)
    return nu.With(
        *(
            nustd.kv.sqlite_navigator_redis(
                str(Path(data) / s.file), tags=(s.root,), redis_url=url, channel_prefix=s.channel
            )
            for s in STORES
        )
    )


def init_stores() -> nu.Nu:
    """Every core store's fixed containers, made where missing: one commit per store."""
    return nu.Sequential(*(nustd.kv.atomic(s.init()) for s in STORES))


def kernel_open(
    body: nu.Nu,
    *,
    data: str,
    name: str = "nuspace-test",
    spares: int = 0,
    grace: float = 2.0,
    **bound: object,
) -> nu.With:
    """The kernel open on the space whose data dir is ``data``, beside ``body``.

    The open's order: server and stores, a dict, the containers, reap;
    then the pool (spare workers, each opening the stores itself), the
    backends and config, and inside them the kernel racing ``body``. Reap
    needs no backend, so nothing is spawned before it.
    """
    (Path(data) / "store").mkdir(parents=True, exist_ok=True)
    served = nu.With(nustd.valkey.server(Path(data) / VALKEY_DIR), navigators(data))
    pool = nustd.mp_pool.pool(name=name, init=navigators(data), spares=spares, grace=grace)
    drivers = nu.With(pool, kernel.bound(**bound), body=nu.Race(kernel.kernel(), body))
    return nu.With(
        served,
        nu.Provide(dict, {}),
        body=init_stores() >> kernel.reap() >> drivers,
    )


# --- The harness ------------------------------------------------------------------


class _Hold(ScalarQuery):
    """Hands the host context to ``opened``, then waits for ``done``."""

    def __init__(self, opened: asyncio.Future, done: asyncio.Event) -> None:
        super().__init__()
        self._payload = {"opened": opened, "done": done}

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        opened, done = self._payload["opened"], self._payload["done"]

        async def athunk(rt: object) -> object:
            opened.set_result(rt.ctx)
            await done.wait()

        return athunk


@dataclass
class Kernel:
    """An open kernel: run ops against it, read the store, wait for the kernel."""

    ctx: nu.Context
    done: asyncio.Event
    task: asyncio.Task
    data: str

    async def run(self, term: nu.Nu) -> object:
        value, _ = await nu.arun(term, self.ctx)
        return value

    async def read(self, term: nu.Nu) -> object:
        return await self.run(nuspace.atomic(term))

    async def do(self, term: nu.Nu) -> object:
        """``term`` in one commit: ``nuspace.atomic``."""
        return await self.run(nuspace.atomic(term))

    async def made(self, term: nu.Nu) -> object:
        """Run ``term``, an op given ``into=MADE``, in one commit, and read what it set there."""
        await self.do(term)
        return await self.run(MADE)

    async def until(
        self, read: Callable[[], object], pred: Callable[[object], bool], timeout: float = 4.0
    ) -> object:
        """Call ``read`` (a coroutine function) until ``pred`` holds on it, or fail with the last value."""
        deadline = time.monotonic() + timeout
        while True:
            value = await read()
            if pred(value):
                return value
            if time.monotonic() > deadline:
                msg = f"timed out waiting, last read: {value!r}"
                raise AssertionError(msg)
            await asyncio.sleep(0.05)

    async def row(self, plane_run: str) -> dict:
        """A plane run as a dict: its record, its cell runs oldest first, its workers.

        ``cells`` lists the records of every cell run it ever had, each with
        its ``id``; ``workers`` every worker it ever held, each a record with
        its ``id``. Reads history, test only.
        """
        rec = await self.read(Space.exec.plane_runs[plane_run].extract())
        node = Space.exec.indexes.history.plane_to_plane_runs[rec["plane"]].runs[plane_run]
        by_cell = await self.read(node.cell_to_cell_runs.extract()) or {}
        ids = sorted(cr for runs in by_cell.values() for cr in runs.get("ids", {}))
        cells = [{"id": cr, **await self.read(Space.exec.cell_runs[cr].extract())} for cr in ids]
        held = await self.read(node.workers.extract()) or {}
        workers = [
            {"id": w, **await self.read(Space.exec.workers[w].extract())} for w in sorted(held)
        ]
        return {"id": plane_run, **rec, "cells": cells, "workers": workers}

    async def run_row(
        self, plane_run: str, pred: Callable[[dict], bool], timeout: float = 4.0
    ) -> dict:
        """The plane run as :meth:`row` reads it, until ``pred`` holds on it."""
        return await self.until(lambda: self.row(plane_run), pred, timeout)

    async def live(self) -> dict:
        """``indexes.live``, whole. Test only."""
        return await self.read(Space.exec.indexes.live.extract())

    async def plane(self, *progs: str, backend: str = "async") -> tuple[str, list[str]]:
        """A plane on ``backend`` with a cell per prog: its id and its cells' ids."""
        p = await self.made(nuspace.plane.add(backend=backend, into=MADE))
        return p, [await self.made(nuspace.cell.add(p, src, into=MADE)) for src in progs]

    async def start(self, plane: str, **kwargs: object) -> str:
        """A plane run of ``plane`` asked for: its id."""
        return await self.made(nuspace.plane_run.add(plane, into=MADE, **kwargs))

    async def close(self) -> None:
        if not self.task.done():
            self.done.set()
            await asyncio.wait_for(self.task, 15)


def ended(row: dict) -> bool:
    """A plane run, cell run or worker row that has ended."""
    return row.get("ended_at") is not None


def live(row: dict) -> bool:
    """A plane run or cell run row that started and has not ended."""
    return row.get("started_at") is not None and not ended(row)


def cell_of(row: dict, cell: str) -> dict:
    """The newest cell run of ``cell`` in a plane run row, ``{}`` when none."""
    mine = [c for c in row.get("cells", []) if c["cell"] == cell]
    return mine[-1] if mine else {}


def only_cell(row: dict) -> dict:
    """The one cell run of a plane run row."""
    (cr,) = row["cells"]
    return cr


def texts(row: dict, stream: str | None = None) -> list[str]:
    """The text of each output entry of a cell run row, of ``stream`` only when given."""
    return [text for _, s, text in row.get("out") or [] if stream is None or s == stream]


def workers_named(prefix: str) -> list:
    """Pool workers still up under ``prefix``: each one runs titled ``nu:{prefix}-{wid}``."""
    return [p for p in multiprocessing.active_children() if p.name.startswith(f"nu:{prefix}")]


async def opened(
    name: str = "nuspace-test", *, data: str | None = None, **kwargs: object
) -> Kernel:
    """A kernel open on this loop, held until :meth:`Kernel.close`. ``data`` None is a fresh dir."""
    data = data or tempfile.mkdtemp(prefix="nuspace-kernel-")
    loop = asyncio.get_running_loop()
    ready, done = loop.create_future(), asyncio.Event()
    hold = nu.With(MADE_STORE, body=nu.let(_Hold(ready, done), lambda _: nu.Noop()))
    task = asyncio.create_task(nu.arun(kernel_open(hold, data=data, name=name, **kwargs)))
    waiting = asyncio.ensure_future(asyncio.shield(ready))
    finished, _ = await asyncio.wait({waiting, task}, timeout=30, return_when="FIRST_COMPLETED")
    if task in finished:
        task.result()
    ctx = await waiting
    return Kernel(ctx, done, task, data)
