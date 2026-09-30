"""Small things services share: waiting on the store, re-entering on a change.

Every service runs on a worker and hears the store through the host's feed.
A subscription opened after a read can miss a write landing in between, so
each wait here also reads again every :data:`~.kernel.utils.WATCH_SECONDS`:
a change is late at worst, never lost. Every read and every subscription
carries its own snapshot, so the kv pass a run gets finds nothing left to
bracket and never holds a transaction open across a wait.
"""

from __future__ import annotations

import nu
from nuspace.ops.utils import text

from .kernel.utils import Ticking, park, snap, until, wake


__all__ = ["Ticking", "follows", "moved", "park", "snap", "until", "wake"]


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
        ref: A str leaf in the store.
        name: The attr the value is bound under, per turn.
        body: What runs while the value holds.
        alive: Whether ``ref``'s row is still there, read per turn. Once it
            reads False the turn parks rather than subscribing to a row that
            is gone, and waits to be cancelled (eg by the fold over the rows).
    """
    turn = nu.Race(body >> park(), moved(ref, nu.StrRef(name)))
    if alive is not None:
        turn = nu.IfDo(snap(alive), turn, park())
    return nu.ForeverDo(nu.Let(name, snap(text(ref)), turn))
