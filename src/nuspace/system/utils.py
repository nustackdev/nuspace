"""Small things services share: waiting on the store, re-entering on a change.

Every service runs on a worker and hears the store through the host's feed.
A subscription opened after a read can miss a write landing in between, so
each wait here also reads again every :data:`~.kernel.body.WATCH_SECONDS`:
a change is late at worst, never lost. Every read and every subscription
carries its own snapshot, so the kv pass a run gets finds nothing left to
bracket and never holds a transaction open across a wait.
"""

from __future__ import annotations

import nu
from nuspace.ops.utils import text

from .kernel.body import WATCH_SECONDS
from .kernel.utils import park, snap


__all__ = ["follows", "moved", "park", "snap", "wake"]


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
