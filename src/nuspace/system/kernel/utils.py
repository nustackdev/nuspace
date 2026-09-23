"""Small things the kernel's modules share. Helpers, not concepts."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import nu
import nustd.kv
from nu.lang import ScalarQuery
from nuspace.shapes import Space


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.lang.runtime import Runtime


__all__ = ["PARK_SECONDS", "Now", "park", "snap"]


#: How long a parked branch sleeps between doing nothing.
PARK_SECONDS = 3600.0


class Now(ScalarQuery):
    """Seconds since the epoch, read when evaluated.

    Hand written so a body holding it pickles: ``nustd.time.time()`` builds
    a ``nu.host`` atom whose class pickle cannot find by name.
    """

    def __init__(self) -> None:
        super().__init__()

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        def thunk(rt: Runtime) -> object:
            return time.time()

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        async def athunk(rt: Runtime) -> object:
            return time.time()

        return athunk


def park() -> nu.Nu:
    """Sit until cancelled. What an arm does instead of ending, so a fold does not respawn it."""
    return nu.ForeverDo(nu.Delay(PARK_SECONDS))


def snap(term: nu.Nu) -> nu.Nu:
    """``term`` read in a snapshot of the Space store."""
    return nustd.kv.Snapshot(term, scope=Space)
