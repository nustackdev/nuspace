"""Terms test programs use to misbehave on a worker. A module of its own so a worker can import it.

Each acts when evaluated, never when built: building a program happens in
the host too (``add_cell`` works out ``has_ui`` by constructing it).
"""

from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING

from nu.lang import ScalarQuery


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.lang.runtime import Runtime


class Block(ScalarQuery):
    """Holds the loop it runs on for ``seconds``, so nothing else on it runs meanwhile."""

    def __init__(self, seconds: float) -> None:
        super().__init__()
        self._payload = {"seconds": seconds}

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        def thunk(rt: Runtime) -> object:
            time.sleep(self._payload["seconds"])

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        async def athunk(rt: Runtime) -> object:
            time.sleep(self._payload["seconds"])  # blocking is the point

        return athunk


class Crash(ScalarQuery):
    """Ends the process it runs in, at once, with ``code``."""

    def __init__(self, code: int = 3) -> None:
        super().__init__()
        self._payload = {"code": code}

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        def thunk(rt: Runtime) -> object:
            os._exit(self._payload["code"])

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        async def athunk(rt: Runtime) -> object:
            os._exit(self._payload["code"])

        return athunk
