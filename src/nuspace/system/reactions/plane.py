"""The reactions plane: runs a plane when something changes. No engine of its own.

The plane runs its cells like any plane, on the ``async`` backend, and
init boots it. Its first cell, :data:`PARK`, runs ``nu.Park()``: it never
ends, so the plane run stays live with no reactions at all, and reload
gives each new reaction cell its first run in it. Every other cell is a
reaction (see :mod:`.ops`), whose program is :func:`react`::

    nu.ReactEvery(change, up_plane(plane, reaction))

An event flow: each notification of ``change`` runs :func:`up_plane` once,
in order, and nothing else does, not the add, not a boot, no re-check. A
change landing while the run it asked for last is live adds nothing, so a
burst gives one run. Best effort, as event flows are: a change landing
during a live run, before the reaction subscribes, or while the space is
closed, is missed. A plane that must not miss one watches on a level flow
of its own.

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

from .shapes import PLANE, Reaction


__all__ = ["BACKEND", "PARK", "PARK_PROG", "react", "up_plane"]


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


def up_plane(plane: nu.StrArg, reaction: nu.StrArg) -> nu.Nu:
    """Run a plane once more for a reaction, unless the run it asked for last is still live.

    The reaction keeps the plane run it last asked for in its own cell
    state (:attr:`~.shapes.Reaction.run`), so whether that run is still
    live is one point read, whatever else runs the plane. With it ended,
    one is added now. With it live, nothing is added: the change that asked
    is missed, so never two of its runs at once. A plane gone or removed
    gets nothing. Never waits.

    Two commits: the run (Space, the check and the add), then the id kept
    (State). :func:`react` runs it once per notification, one at a time,
    so no newer change lands between them. A cancel of the whole flow (the
    reaction removed) between them leaves that run untracked.

    Args:
        plane: The plane to run.
        reaction: The reaction's id: what the run is recorded ``by``, and
            whose cell state keeps it.
    """
    held = at.cell(id=reaction).state(Reaction).run
    free = Space.exec.indexes.live.plane_runs.contains(held.fallback("")).not_()

    def write(new: nu.ObjectRef) -> nu.Nu:
        asked = free.and_(ops.plane.exists(plane))
        return atomic(nu.IfDo(asked, ops.plane_run.add(plane, by=reaction, into=new))) >> atomic(
            nu.IfDo(nu.Str(new) != "", held.set(nu.Str(new)))
        )

    return nu.let("", write)


def react(change: nu.Nu, plane: nu.StrArg, reaction: nu.StrArg) -> nu.Nu:
    """A reaction's whole program: :func:`up_plane` on every notification of ``change``.

    One at a time, in order: :func:`up_plane` never waits, so the backlog
    stays short, and a newer change never cancels one between its commits.
    What a reaction cell's prog calls (see :func:`~.ops.source`), so the
    stored source names this one entry and nothing internal. A raise is
    reported on the cell run's output and the flow runs again.

    Args:
        change: A subscription, eg ``nuspace.at.plane(id="chat").state(Inbox).messages.on_change()``.
        plane: The plane it runs.
        reaction: The reaction's id.
    """
    flow = nu.ReactEvery(atomic(change), up_plane(plane, reaction))
    return restarting(flow, PLANE, reaction)
