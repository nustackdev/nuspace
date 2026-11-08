"""Shared fixtures: a space's stores (Space, State, Web, Conn) held open across evaluations.

``store`` is in memory. A test module that sets ``STORES`` to backend names
(``"memory"``, ``"sqlite"``) runs each of its ``store`` tests once per name.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pytest_asyncio
from _support.made import MADE, MADE_STORE

import nu
import nustd.kv
from nu.lang import ScalarQuery
from nuspace.devices.web.stores import CONN_STORE, WEB_STORE
from nuspace.host.stores import SPACE_STORE, STATE_STORE


if TYPE_CHECKING:
    from collections.abc import Callable


# The tests' specs register (nuspace_testing, _support.specs), here and on every worker.
os.environ["NUSPACE_TESTING"] = "1"

# No test run sends telemetry, from a checkout or an installed wheel. The tests of
# telemetry itself unset it and stub the POST.
os.environ["NUSPACE_TELEMETRY"] = "0"


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
    """``run`` evaluates an op as is, ``read`` inside ``atomic``, a snapshot of each store it reads.

    ``made`` runs an op that sets ``into`` and reads it back.
    """

    ctx: nu.Context

    async def run(self, term: nu.Nu) -> object:
        value, _ = await nu.arun(term, self.ctx)
        return value

    async def read(self, term: nu.Nu) -> object:
        return await self.run(nustd.kv.atomic(term))

    async def made(self, term: nu.Nu) -> object:
        """Run ``term``, an op given ``into=MADE``, and read what it set there."""
        await self.run(term)
        return await self.run(MADE)


def pytest_generate_tests(metafunc):
    """A module's ``STORES``, when it names any, parametrize every test using ``store``."""
    backends = getattr(metafunc.module, "STORES", ())
    if backends and "store" in metafunc.fixturenames:
        metafunc.parametrize("store", backends, indirect=True)


#: Every store of a space with the web device on, in the order they are made.
STORES_OF_A_SPACE = (SPACE_STORE, STATE_STORE, WEB_STORE, CONN_STORE)


def _navigators(backend: str, root: Path) -> tuple[nu.Nu, ...]:
    """Every store's navigator on one backend: in memory, or the space's sqlite files under ``root``."""
    if backend == "sqlite":
        return tuple(
            nustd.kv.sqlite_navigator(str(root / s.file), tags=(s.root,)) for s in STORES_OF_A_SPACE
        )
    return tuple(nustd.kv.memory_navigator(tags=(s.root,)) for s in STORES_OF_A_SPACE)


def init_stores() -> nu.Nu:
    """Every store's fixed containers, made where missing: one commit per store."""
    return nu.Sequential(*(nustd.kv.atomic(s.init()) for s in STORES_OF_A_SPACE))


@pytest_asyncio.fixture
async def store(request, tmp_path):
    loop = asyncio.get_running_loop()
    opened, done = loop.create_future(), asyncio.Event()
    navigators = _navigators(getattr(request, "param", "memory"), tmp_path / "space")
    held = asyncio.create_task(nu.arun(nu.With(*navigators, MADE_STORE, body=_Hold(opened, done))))
    ctx = await opened
    held_store = Store(ctx)
    await held_store.run(init_stores())
    yield held_store
    done.set()
    await held


@dataclass
class DiskStore(Store):
    """The same calls against the space's sqlite files, opened per evaluation. A few tests only."""

    path: str = ""

    async def run(self, term: nu.Nu) -> object:
        stack = nu.With(*_navigators("sqlite", Path(self.path)))
        value, _ = await nu.arun(nu.With(stack, body=term))
        return value


@pytest_asyncio.fixture
async def disk(tmp_path):
    held = DiskStore(ctx=None, path=str(tmp_path / "space"))
    await held.run(init_stores())
    return held
