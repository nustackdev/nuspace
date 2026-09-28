"""The kernel harness and programs shared by the kernel, services and host tests.

One kernel held open on the test's loop: run ops against it, read the store, wait
until the kernel has made something true.
"""

from __future__ import annotations

import asyncio
import multiprocessing
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import nu
from nu.lang import ScalarQuery
from nuspace import ops
from nuspace.shapes import Space
from nuspace.system.kernel import open_kernel


if TYPE_CHECKING:
    from collections.abc import Callable


# --- Programs ------------------------------------------------------------------

_HEAD = """
import nu
import nustd.kv
import nuspace

class Tick(nuspace.CellState):
    n = nustd.kv.IntRef.slot()
    s = nustd.kv.StrRef.slot()

def out():
"""


def prog(*lines: str) -> str:
    """A program with ``Tick`` declared, whose ``out`` runs ``lines``."""
    return _HEAD + "".join(f"    {line}\n" for line in lines)


SET_42 = prog("return Tick.n.set(42)")
RAISES = prog('raise ValueError("boom")')
FOREVER = prog('print("built")', 'return nu.print("tick") >> nu.ForeverDo(nu.Delay(0.05))')
READS_TAG = prog('return Tick.s.set(nu.StrAttrRef("test.tag"))')
#: Holds its worker's loop, so it never hears an interrupt.
BLOCKS = prog(
    "from _support.actions import Block",
    "return nu.Delay(0.2) >> nu.Let('x', Block(60), nu.Noop())",
)
#: Takes its own worker process down, a moment in.
CRASHES = prog(
    "from _support.actions import Crash", "return nu.Delay(0.3) >> nu.Let('x', Crash(3), nu.Noop())"
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

    async def run(self, term: nu.Nu) -> object:
        value, _ = await nu.arun(term, self.ctx)
        return value

    async def read(self, term: nu.Nu) -> object:
        return await self.run(ops.snapshot(term))

    async def until(
        self, term: nu.Nu, pred: Callable[[object], bool], timeout: float = 4.0
    ) -> object:
        """Read ``term`` until ``pred`` holds on it, or fail with the last value."""
        deadline = time.monotonic() + timeout
        while True:
            value = await self.read(term)
            if pred(value):
                return value
            if time.monotonic() > deadline:
                msg = f"timed out waiting, last read: {value!r}"
                raise AssertionError(msg)
            await asyncio.sleep(0.05)

    async def run_row(self, rid: str, pred: Callable[[dict], bool], timeout: float = 4.0) -> dict:
        """The plane run, read by id until ``pred`` holds on it."""
        return await self.until(ops.run(rid), pred, timeout)

    async def worker_row(
        self, wid: str, pred: Callable[[dict], bool] | None = None, timeout: float = 4.0
    ) -> dict:
        """A worker's record, live or ended. With ``pred``, read until it holds; by default until ended."""
        return await self.until(worker(wid), pred or ended, timeout)

    async def plane(self, *progs: str, backend: str = "async") -> tuple[str, list[str]]:
        p = await self.run(ops.add_plane(ui=True, backend=backend))
        return p, [await self.run(ops.add_cell(p, src)) for src in progs]

    async def close(self) -> None:
        if not self.task.done():
            self.done.set()
            await asyncio.wait_for(self.task, 15)


def ended(row: dict) -> bool:
    """A run or cell run row that has ended."""
    return row.get("terminated_at") is not None


def live(row: dict) -> bool:
    """A run or cell run row that started and has not ended."""
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
    return [text for _, s, text in row["out"] if stream is None or s == stream]


def worker(wid: str) -> nu.Nu:
    """One worker record as a dict, any worker, by id. Tests only read ended ones this way."""
    row = Space.kernel.workers[wid]

    def read(ref: nu.Nu, default: object) -> nu.Nu:
        return nu.If(ref.exists(), ref, nu.Literal(default))

    return nu.Dict.of(
        id=wid,
        backend=read(row.backend, ""),
        run=read(row.run, ""),
        handle=read(row.handle, ""),
        started_at=read(row.started_at, None),
        terminated_at=read(row.terminated_at, None),
        exit=read(row.exit, ""),
        error=read(row.error, ""),
    )


def history(plane: str | None = None) -> nu.Nu:
    """Every plane run ever, oldest first, as :func:`nuspace.ops.run` rows. Test only: O(n)."""
    item = "test.history"
    rid = nu.StrAttrRef(item)
    ids: nu.Nu = nu.list(Space.kernel.runs.keys())
    if plane is not None:
        ids = nu.Filter(ids, nu.Eq(Space.kernel.runs[rid].plane, plane), key=item)
    return nu.Collect(nu.Map(ids, ops.run(rid), key=item))


def workers_named(prefix: str) -> list:
    return [p for p in multiprocessing.active_children() if p.name.startswith(prefix)]


async def opened(name: str = "nuspace-test", **kwargs: object) -> Kernel:
    """A kernel open on this loop, held until :meth:`Kernel.close`."""
    loop = asyncio.get_running_loop()
    ready, done = loop.create_future(), asyncio.Event()
    body = nu.Let("test.held", _Hold(ready, done), nu.SetCmd(nu.AnyAttrRef("test.x"), 1))
    task = asyncio.create_task(nu.arun(open_kernel(body, name=name, **kwargs)))
    ctx = await asyncio.wait_for(asyncio.shield(ready), 20)
    return Kernel(ctx, done, task)
