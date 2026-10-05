"""Shared fixtures: the Space and States stores held open across evaluations.

``store`` is in memory. A test module that sets ``STORES`` to backend names
(``"memory"``, ``"sqlite"``) runs each of its ``store`` tests once per name.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pytest_asyncio
from _support.made import MADE, MADE_STORE

import nu
import nustd.kv
from nu.lang import ScalarQuery
from nuspace import ops
from nuspace.shapes import Space, States
from nuspace.system.kernel import KERNEL_FILE, STATE_FILE


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
    """``run`` evaluates an op as is, ``read`` inside a Snapshot of both stores.

    ``made`` runs an op that sets ``into`` and reads it back.
    """

    ctx: nu.Context

    async def run(self, term: nu.Nu) -> object:
        value, _ = await nu.arun(term, self.ctx)
        return value

    async def read(self, term: nu.Nu) -> object:
        return await self.run(ops.snapshot(term))

    async def made(self, term: nu.Nu) -> object:
        """Run ``term``, an op given ``into=MADE``, and read what it set there."""
        await self.run(term)
        return await self.run(MADE)


def pytest_generate_tests(metafunc):
    """A module's ``STORES``, when it names any, parametrize every test using ``store``."""
    backends = getattr(metafunc.module, "STORES", ())
    if backends and "store" in metafunc.fixturenames:
        metafunc.parametrize("store", backends, indirect=True)


def _navigators(backend: str, root: Path) -> tuple[nu.Nu, nu.Nu]:
    """The Space and States navigators of one backend: in memory, or the space's two sqlite files."""
    if backend == "sqlite":
        root.mkdir(parents=True, exist_ok=True)
        return (
            nustd.kv.sqlite_navigator(str(root / KERNEL_FILE), tags=(Space,)),
            nustd.kv.sqlite_navigator(str(root / STATE_FILE), tags=(States,)),
        )
    return nustd.kv.memory_navigator(tags=(Space,)), nustd.kv.memory_navigator(tags=(States,))


@pytest_asyncio.fixture
async def store(request, tmp_path):
    loop = asyncio.get_running_loop()
    opened, done = loop.create_future(), asyncio.Event()
    navigators = _navigators(getattr(request, "param", "memory"), tmp_path / "space")
    held = asyncio.create_task(nu.arun(nu.With(*navigators, MADE_STORE, body=_Hold(opened, done))))
    ctx = await opened
    yield Store(ctx)
    done.set()
    await held


@dataclass
class DiskStore(Store):
    """The same calls against the space's two sqlite files, opened per evaluation. A few tests only."""

    path: str = ""

    async def run(self, term: nu.Nu) -> object:
        stack = nu.With(
            nustd.kv.sqlite_navigator(str(Path(self.path) / KERNEL_FILE), tags=(Space,)),
            nustd.kv.sqlite_navigator(str(Path(self.path) / STATE_FILE), tags=(States,)),
        )
        value, _ = await nu.arun(nu.With(stack, body=term))
        return value


@pytest_asyncio.fixture
async def disk(tmp_path):
    return DiskStore(ctx=None, path=str(tmp_path / "space"))
