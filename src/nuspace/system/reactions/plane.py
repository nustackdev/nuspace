"""The reactions plane: runs a plane when something changes. No engine of its own.

The plane runs its cells like any plane, on the ``async`` backend, and
init boots it. Its first cell, :data:`PARK`, runs ``nu.Park()``: it never
ends, so the plane run stays live with no reactions at all, and reload
gives each new reaction cell its first run in it. Every other cell is a
reaction (see :mod:`.ops`), whose program is :func:`react`::

    nu.ReactLatest(change, up_plane(plane, reaction))

An event flow: each notification of ``change`` runs :func:`up_plane` once,
and nothing else does, not the add, not a boot, no re-check. A newer
notification restarts an :func:`up_plane` still waiting, so a burst merges
into one run after the live one. Best effort, as event flows are: a change
landing before the reaction subscribes, or while the space is closed, is
missed. A plane that must not miss one watches on a level flow of its own.

Contract for the planes a reaction runs: they run to completion, keep a
cursor in their state and handle everything past it, so an extra run is
harmless and a plane writing what it reacts to settles.
"""

from __future__ import annotations

import nu
from nuspace import ops
from nuspace.ops.brackets import atomic
from nuspace.places import at
from nuspace.shapes import Space
from nuspace.utils.policies import restarting

from .shapes import Reaction, Registry


__all__ = ["BACKEND", "PARK", "PARK_PROG", "PLANE", "react", "registry", "up_plane"]


#: The plane's id, fixed.
PLANE = "reactions"

#: Its fixed first cell, the one that keeps its run live.
PARK = "reactions_park"

#: What its runs execute on.
BACKEND = "async"

#: The park cell's prog.
PARK_PROG = """\
import nu


def out():
    return nu.Park()
"""


def registry() -> Registry:
    """The plane's state: ``State.planes["reactions"]`` read through :class:`~.shapes.Registry`."""
    return at.plane(id=PLANE).state(Registry)


def up_plane(plane: nu.StrArg, reaction: nu.StrArg) -> nu.Nu:
    """Run a plane once more for a reaction, never two of its runs at once. Returns once asked for.

    The reaction keeps the plane run it last asked for in its own cell
    state (:attr:`~.shapes.Reaction.run`), so whether that run is still
    live is one point read, whatever else runs the plane. With it ended,
    one is added now. With it live, it may or may not see what asked for
    this, so this waits until it ends (a level wait with the standard
    re-checks), then adds one. A plane gone or removed gets nothing.
    Cancelled while it waits, it adds nothing.

    Two commits: the run (Space, the check and the add), then the id kept
    (State). A cancel landing between them leaves that run untracked, so
    the next call may add one beside it: the contract makes it harmless.

    Args:
        plane: The plane to run.
        reaction: The reaction's id: what the run is recorded ``by``, and
            whose cell state keeps it.
    """
    held = at.cell(id=reaction).state(Reaction).run
    free = Space.exec.indexes.live.plane_runs.contains(held.fallback("")).not_()
    settled = nu.WaitUntil(
        atomic(ops.plane_run.on_live_change(plane=plane)),
        atomic(free),
        after=nu.RECHECK_AFTER,
        every=nu.RECHECK_EVERY,
    )

    def write(new: nu.ObjectRef) -> nu.Nu:
        asked = free.and_(ops.plane.exists(plane))
        return atomic(nu.IfDo(asked, ops.plane_run.add(plane, by=reaction, into=new))) >> atomic(
            nu.IfDo(nu.Str(new) != "", held.set(nu.Str(new)))
        )

    return settled >> nu.let("", write)


def react(change: nu.Nu, plane: nu.StrArg, reaction: nu.StrArg) -> nu.Nu:
    """A reaction's whole program: :func:`up_plane` on every notification of ``change``.

    What a reaction cell's prog calls (see :func:`~.ops.source`), so the
    stored source names this one entry and nothing internal. A raise is
    reported on the cell run's output and the flow runs again.

    Args:
        change: A subscription, eg ``nuspace.at.plane(id="chat").state(Inbox).messages.on_change()``.
        plane: The plane it runs.
        reaction: The reaction's id.
    """
    flow = nu.ReactLatest(atomic(change), up_plane(plane, reaction))
    return restarting(flow, PLANE, reaction)
