"""Small things the kernel's modules share. Helpers, not concepts."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any

import nu
import nustd.kv
from nu.lang import ScalarQuery
from nu.lang.sentinels import EMPTY, INVALID
from nuspace.shapes import Space, States


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.lang.runtime import Runtime


__all__ = ["PARK_SECONDS", "WATCH_SECONDS", "Now", "Ticking", "park", "snap", "until", "wake"]


#: How long a parked branch sleeps between doing nothing.
PARK_SECONDS = 3600.0

#: How long a wait trusts its subscription before reading again. A change
#: landing between a read and the subscribe is caught this late.
WATCH_SECONDS = 1.0


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
    """``term`` read in a snapshot of both stores, each opened only if read."""
    return nustd.kv.Snapshot(nustd.kv.Snapshot(term, scope=States), scope=Space)


def wake(change: nu.Nu) -> nu.Nu:
    """Return on one notification from ``change``, or after a watch period.

    Args:
        change: A subscription, eg ``ref.on_change()``. Unbracketed: it is
            snapshotted here.
    """
    return nu.Timeout(WATCH_SECONDS, nu.React(snap(change)), on_timeout=nu.Delay(0.0))


def until(cond: nu.Nu, change: nu.Nu) -> nu.Nu:
    """Wait until ``cond`` reads true, woken by ``change``. Returns at once if it does.

    Both unbracketed: each read and each subscription is snapshotted here,
    so nothing holds a transaction across the wait. Read again at least
    every :data:`WATCH_SECONDS`, so a change landing between the read and
    the subscribe is late rather than lost.
    """
    return nu.WhileDo(nu.Not(snap(cond)), wake(change))


class _TickingSubscription:
    """A subscription that also fires every ``seconds``, with key ``None``."""

    def __init__(self, inner: Any, seconds: float) -> None:  # noqa: ANN401 -- any Subscription
        self._inner = inner
        self._seconds = seconds
        self._ticks: dict[int, asyncio.TimerHandle] = {}

    def bind(self, receiver: Callable[[Any], None]) -> None:
        self._inner.bind(receiver)
        loop = asyncio.get_running_loop()

        def tick() -> None:
            self._ticks[id(receiver)] = loop.call_later(self._seconds, tick)
            receiver(None)

        self._ticks[id(receiver)] = loop.call_later(self._seconds, tick)

    def unbind(self, receiver: Callable[[Any], None]) -> None:
        handle = self._ticks.pop(id(receiver), None)
        if handle is not None:
            handle.cancel()
        self._inner.unbind(receiver)

    def close(self) -> None:
        for handle in self._ticks.values():
            handle.cancel()
        self._ticks.clear()
        self._inner.close()


class Ticking(ScalarQuery):
    """``change``, firing as well every :data:`WATCH_SECONDS` (D38).

    What a fold subscribes with: ``ForEachParReactive`` reads its elements
    again only when its subscription fires, so a write the subscription
    missed (landing before it was bound, or a receiver the host's feed
    dropped) would never be seen. A tick makes it late at worst, never lost.

    Args:
        change: A subscription, eg ``ref.on_children_change()``.

    Yields:
        The subscription, wrapped. INVALID when ``change`` is.
    """

    def __init__(self, change: nu.Nu, seconds: float = WATCH_SECONDS) -> None:
        super().__init__(change)
        self._payload = {"seconds": float(seconds)}

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        def thunk(rt: Runtime) -> object:
            msg = "Ticking requires an async runtime; use arun"
            raise RuntimeError(msg)

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        (change,) = children
        seconds = self._payload["seconds"]

        async def athunk(rt: Runtime) -> object:
            sub = await change(rt)
            if sub is EMPTY or sub is INVALID:
                return INVALID
            return _TickingSubscription(sub, seconds)

        return athunk
