"""Shared fixtures: an in memory Space store held open across evaluations."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest_asyncio

import nu
import nustd.kv
from nu.lang import ScalarQuery
from nuspace.shapes import Space
from nuspace.system.kernel import KERNEL_FILE


if TYPE_CHECKING:
    from collections.abc import Callable


class _Hold(ScalarQuery):
    """Hands the ctx it runs in to ``opened``, then waits for ``done``.

    Inside ``nu.With(memory_navigator(...))`` that ctx has the whole stack
    bound, and it stays bound until ``done`` is set, so many terms can be
    evaluated against one in memory store.
    """

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
class Store:
    """``run`` evaluates an op as is, ``read`` inside a Snapshot."""

    ctx: nu.Context

    async def run(self, term: nu.Nu) -> object:
        value, _ = await nu.arun(term, self.ctx)
        return value

    async def read(self, term: nu.Nu) -> object:
        return await self.run(nustd.kv.Snapshot(term, scope=Space))


@pytest_asyncio.fixture
async def store():
    loop = asyncio.get_running_loop()
    opened, done = loop.create_future(), asyncio.Event()
    held = asyncio.create_task(
        nu.arun(nu.With(nustd.kv.memory_navigator(tags=(Space,)), body=_Hold(opened, done)))
    )
    ctx = await opened
    yield Store(ctx)
    done.set()
    await held


@dataclass
class DiskStore(Store):
    """The same calls against the space's sqlite file, opened per evaluation. A few tests only."""

    path: str = ""

    async def run(self, term: nu.Nu) -> object:
        stack = nustd.kv.sqlite_navigator(self.path, tags=(Space,))
        value, _ = await nu.arun(nu.With(stack, body=term))
        return value


@pytest_asyncio.fixture
async def disk(tmp_path):
    return DiskStore(ctx=None, path=str(tmp_path / "space" / KERNEL_FILE))
