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
import nustd.kv
from nu.lang import ScalarQuery
from nuspace import ops
from nuspace.shapes import STATUS_DEAD, STATUS_UP, Space
from nuspace.system.kernel import open_kernel


if TYPE_CHECKING:
    from collections.abc import Callable


# --- programs ------------------------------------------------------------------

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


# --- the harness ------------------------------------------------------------------


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
        return await self.run(nustd.kv.Snapshot(term, scope=Space))

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

    async def run_row(self, rid: str, pred: Callable[[dict], bool]) -> dict:
        rows = await self.until(ops.runs(), lambda rs: pred(_by_id(rs, rid)))
        return _by_id(rows, rid)

    async def worker_row(
        self, wid: str, pred: Callable[[dict], bool], timeout: float = 4.0
    ) -> dict:
        rows = await self.until(ops.workers(), lambda ws: pred(_by_id(ws, wid)), timeout)
        return _by_id(rows, wid)

    async def plane(self, *progs: str) -> tuple[str, list[str]]:
        p = await self.run(ops.add_plane(ui=True))
        return p, [await self.run(ops.add_cell(p, src)) for src in progs]

    async def close(self) -> None:
        if not self.task.done():
            self.done.set()
            await asyncio.wait_for(self.task, 15)


def _by_id(rows: list[dict], rid: str) -> dict:
    return next((r for r in rows if r["id"] == rid), {})


def _dead(row: dict) -> bool:
    return row.get("status") == STATUS_DEAD


def _up(row: dict) -> bool:
    return row.get("status") == STATUS_UP


def _texts(row: dict, stream: str | None = None) -> list[str]:
    return [text for _, s, text in row["out"] if stream is None or s == stream]


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
