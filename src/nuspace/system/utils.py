"""Small things services and system cells share: waiting on the store, following it.

Every wait here is a level one: it reads the store after subscribing, again
on every change and on re-checks, so a change its subscription did not
hear is late, never lost. Every read and every subscription carries its own
snapshot, so nothing here holds a bracket open across a wait.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu

from .kernel.utils import park, snap


if TYPE_CHECKING:
    from collections.abc import Callable, Sequence


__all__ = ["drawing", "follows", "moved", "park", "redraw", "redraws", "snap"]


def moved(ref: nu.Nu, seen: nu.StrArg) -> nu.Nu:
    """Wait until the str at ``ref`` no longer reads ``seen``. Returns at once if it does not.

    An unwritten ref reads ``""``, so a deleted row counts as a move.
    """
    return nu.WaitReactive(snap(ref.on_change()), snap(nu.str(ref).fallback("") != seen))


def follows(ref: nu.Nu, body: Callable[[nu.Str], nu.Nu], *, alive: nu.Nu | None = None) -> nu.Nu:
    """``body(value)`` with the str at ``ref`` read into a frame, run again whenever it changes.

    The value is read, held, and raced against :func:`moved`: a change
    cancels the body (its ``finally_`` runs) and the loop comes round with
    the new value. A body that ends early waits for the change parked.
    Never returns.

    Args:
        ref: A str leaf in the store.
        body: Builds what runs while the value holds, from the value read
            this turn.
        alive: Whether ``ref``'s row is still there, read per turn. Once it
            reads False the turn parks rather than subscribing to a row that
            is gone, and waits to be cancelled (eg by the fold over the rows).
    """

    def turn(held: nu.ObjectRef) -> nu.Nu:
        value = nu.Str(held)
        raced = nu.Race(body(value) >> park(), moved(ref, value))
        return raced if alive is None else nu.IfDo(snap(alive), raced, park())

    return nu.ForeverDo(nu.let(snap(nu.str(ref).fallback("")), turn))


class _Drawn(nu.Shape):
    """What a view last drew, to tell a change that shows from one that does not."""

    view = nu.ObjectRef.slot()


def drawing(body: nu.Nu) -> nu.Nu:
    """``body`` with a place to keep what it last drew, for every :func:`redraw` inside it."""
    return nu.Frame(_Drawn, body, view=None)


def redraw(read: nu.Nu, draw: Callable[[nu.ObjectRef], nu.Nu]) -> nu.Nu:
    """``draw(view)`` of what ``read`` reads now, only when it reads otherwise than last drawn.

    A level pass: run it as often as anything might have moved, and an idle
    store draws nothing. Inside :func:`drawing`.

    Args:
        read: The view, one value. Unbracketed: read in a snapshot here.
        draw: Builds the drawing from the view read.
    """

    def look(now: nu.ObjectRef) -> nu.Nu:
        return nu.IfDo(_Drawn.view != now, draw(now) >> _Drawn.view.set(now))

    return nu.let(snap(read), look)


def redraws(
    changes: Sequence[nu.Nu],
    read: nu.Nu,
    draw: Callable[[nu.ObjectRef], nu.Nu],
    *,
    every: float = 30.0,
) -> nu.Nu:
    """:func:`redraw` after subscribing, on every change of any of ``changes``, and on re-checks. Never returns.

    Args:
        changes: Subscriptions that say ``read`` may have moved. Unbracketed:
            each is snapshotted here.
        read: The view, as :func:`redraw` reads it.
        draw: Builds the drawing from the view read.
        every: Seconds between re-checks. A view that moves with the clock
            sets how often it is read again.
    """
    kept = [
        nu.ReconcileReactive(snap(change), redraw(read, draw), every=every) for change in changes
    ]
    return drawing(nu.ParallelAsync(*kept))
