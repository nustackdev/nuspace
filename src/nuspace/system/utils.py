"""Small things services share: waiting on the store, re-entering on a change.

Every service runs on a worker and hears the store through the host's feed.
A subscription opened after a read can miss a write landing in between, so
each wait here also reads again every :data:`~.kernel.body.WATCH_SECONDS`:
a change is late at worst, never lost. Every read and every subscription
carries its own snapshot, so the kv pass a run gets finds nothing left to
bracket and never holds a transaction open across a wait.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import nu
from nu.lang import ScalarQuery
from nu.lang.sentinels import EMPTY, INVALID
from nuspace.ops.utils import text

from .kernel.body import WATCH_SECONDS
from .kernel.utils import park, snap


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.lang.runtime import Runtime


__all__ = ["Ticking", "follows", "moved", "park", "snap", "wake"]


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
        change: a subscription, eg ``ref.on_children_change()``.

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


def wake(change: nu.Nu) -> nu.Nu:
    """Return on one notification from ``change``, or after a watch period.

    Args:
        change: a subscription, eg ``ref.on_change()``. Unbracketed: it is
            snapshotted here.
    """
    return nu.Timeout(WATCH_SECONDS, nu.React(snap(change)), on_timeout=nu.Delay(0.0))


def moved(ref: nu.Nu, seen: nu.StrArg) -> nu.Nu:
    """Wait until the str at ``ref`` no longer reads ``seen``. Returns at once if it does not.

    An unwritten ref reads ``""``, so a deleted row counts as a move.
    """
    return nu.WhileDo(nu.Eq(snap(text(ref)), seen), wake(ref.on_change()))


def follows(ref: nu.Nu, name: str, body: nu.Nu, *, alive: nu.Nu | None = None) -> nu.Nu:
    """``body`` with the str at ``ref`` bound under ``name``, run again whenever it changes.

    The value is read, bound, and raced against :func:`moved`: a change
    cancels ``body`` (its ``finally_`` runs) and the loop comes round with
    the new value. A ``body`` that ends early waits for the change parked.
    Never returns.

    Args:
        ref: a str leaf in the store.
        name: the attr the value is bound under, per turn.
        body: what runs while the value holds.
        alive: whether ``ref``'s row is still there, read per turn. Once it
            reads False the turn parks rather than subscribing to a row that
            is gone, and waits to be cancelled (eg by the fold over the rows).
    """
    turn = nu.Race(body >> park(), moved(ref, nu.StrAttrRef(name)))
    if alive is not None:
        turn = nu.IfDo(snap(alive), turn, park())
    return nu.ForeverDo(nu.Let(name, snap(text(ref)), turn))
