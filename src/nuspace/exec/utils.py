"""The three small things every module in here needs. Helpers, not concepts.

A park, a re-entry on a change, and reading a prop that may never have been
written. None of them is a word from the model, which is why they are here
rather than in a file of their own.
"""

from __future__ import annotations

import nu


__all__ = [
    "PARK_SECONDS",
    "park",
    "prop",
    "reenters_on",
]


#: How long a parked branch sleeps before waking to do nothing. Finite only
#: because ``Delay`` takes a number: a branch that parks is waiting to be
#: cancelled, never to time out.
PARK_SECONDS = 3600.0


def park() -> nu.Nu:
    """Sit on the loop doing nothing until something cancels this branch.

    What a branch with nothing left to do does instead of returning. A
    ``Race`` ends when its first child finishes, so a body that returns
    restarts the loop around it immediately and spins. A fold is the same
    story one level up: it sweeps arms whose task ended and starts them
    again, so a Cell that is meant to stay stopped has to stay running and
    idle rather than end.

    Built fresh at each call site. One node in two tree positions is one
    node, and nothing here is worth sharing.
    """
    return nu.ForeverDo(nu.Delay(nu.Float(PARK_SECONDS)))


def reenters_on(change: nu.Nu, body: nu.Nu, *, when: nu.Nu | None = None) -> nu.Nu:
    """``body``, built again from the store every time ``change`` fires.

    The two race: the notification cancels the body, the loop re-enters, and
    everything the body reads is read again on the way in, subscription
    included. ``body`` is parked behind rather than returned from, so a body
    that ends early waits for the change like a body that never ends.

    Args:
        change: the subscription to re-enter on. Opened fresh on every turn,
            because two positions holding one node hold one handle and the
            first to end closes it under the other.
        body: what runs until the change comes.
        when: gates the subscription. Read once per turn, so the answer can
            change while this is running. False parks that side instead,
            which leaves the body running and nothing watching it, and opens
            no subscription at all.
    """
    wake = nu.React(change, nu.Noop())
    return nu.ForeverDo(
        nu.Race(
            body >> park(),
            wake if when is None else nu.IfDo(when, wake, park()),
        )
    )


def prop(ref: nu.Nu, default: object) -> nu.Nu:
    """What is at ``ref``, or ``default`` where nothing has been written.

    Every prop has a default and an unwritten leaf reads EMPTY, which is not
    a value anything can switch on. Read per turn rather than once at fan
    out, so editing a prop takes effect the next time the branch reading it
    comes round.
    """
    return nu.If(ref.exists(), ref, nu.Literal(default))
