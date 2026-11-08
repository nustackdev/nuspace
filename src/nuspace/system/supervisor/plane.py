"""The supervisor plane: restarts the planes it supervises when their runs end.

One cell, :data:`CELL`, runs :func:`driver`: one arm per supervised plane
(:class:`~.shapes.Policy`), births and deaths included. An arm keeps one
plane run of its plane ``by`` supervisor, remembers its id
(``Supervised.run``), and only ever reads that run:

    no run yet, or one from an earlier open    plane_run.add(by="supervisor"), no wait
    its run live                               left alone until it ends
    its run ended, the policy covers the exit  plane_run.add after the wait
    anything else                              left down until supervised again

=============  ===========================  =====================
policy         restarts after exit          never after
=============  ===========================  =====================
``on-failure`` ``failed``                   ``ok``, ``interrupted``,
``always``     ``ok``, ``failed``           ``killed``
=============  ===========================  =====================

``interrupted`` and ``killed`` are somebody asking, so they are respected.
A run from an earlier open (``created_at`` before ``Space.info.opened_at``)
was ended by reap, so every supervised plane runs again at each open.
init leaves supervised planes to it, so a plane both booted and
supervised gets this one run, not a second one from init.

The wait: the plane's fixed ``delay`` when it has one, read as it falls
due; else a backoff that starts at :data:`BACKOFF_START`, doubles per
restart up to :data:`BACKOFF_CAP`, and starts over after an ``ok`` exit.

An arm is a level flow over its plane's policy, its live runs and its row,
with the standard re-checks, so a missed notification is a late restart,
never a lost one. Every read is a point read. An arm that raises is
reported and runs again after a short delay (``restarting``).
"""

from __future__ import annotations

import nu
from nuspace import ops
from nuspace.ops.brackets import atomic
from nuspace.places import at
from nuspace.shapes import EXIT_FAILED, EXIT_OK, Space
from nuspace.utils.policies import restarting

from .shapes import ALWAYS, Policy


__all__ = [
    "BACKEND",
    "BACKOFF_CAP",
    "BACKOFF_START",
    "BY",
    "CELL",
    "PLANE",
    "PROG",
    "driver",
    "supervised",
]


#: The plane's id, fixed.
PLANE = "supervisor"

#: Its one cell's id, fixed.
CELL = "supervisor_main"

#: What its runs execute on.
BACKEND = "mp"

#: What the plane runs the supervisor asks for are recorded as ``by``.
BY = "supervisor"

#: The first wait before a restart, in seconds.
BACKOFF_START = 0.25

#: The longest wait before a restart, in seconds.
BACKOFF_CAP = 30.0

#: The cell's prog: the driver lives here, the store holds this.
PROG = """\
from nuspace.system.supervisor import plane


def out():
    return plane.driver()
"""

_RECHECK = {"after": nu.RECHECK_AFTER, "every": nu.RECHECK_EVERY}


def supervised() -> nu.Nu:
    """The supervised planes' ref: ``State.planes["supervisor"]`` read through :class:`~.shapes.Policy`."""
    return at.plane(id=PLANE).state(Policy).planes


class _Arm(nu.Shape):
    """What one arm keeps across its passes: the backoff it waits next."""

    delay = nu.FloatRef.slot()


def _start(plane: nu.Str, mine: nu.Str) -> nu.Nu:
    """A new plane run of the plane ``by`` supervisor, then remembered. Two commits.

    The run (Space) is asked for only while the plane is supervised, still
    there and its remembered run is still ``mine``; remembering it (State)
    checks that again. One of them moving in between (an unsupervise, a
    supervise) refuses the second, and the run just asked for, tracked by
    nobody, is stopped.
    """
    row = supervised()[plane]
    still = row.policy.exists().and_(row.run.fallback("") == mine)

    def write(new: nu.ObjectRef) -> nu.Nu:
        asked = still.and_(ops.plane.exists(plane))
        made = nu.Str(new) != ""
        orphan = made.and_(row.run.fallback("") != nu.Str(new))
        return (
            atomic(nu.IfDo(asked, ops.plane_run.add(plane, by=BY, into=new)))
            >> atomic(nu.IfDo(made.and_(still), row.run.set(nu.Str(new))))
            >> nu.IfDo(atomic(orphan), atomic(ops.plane_run.stop(nu.Str(new))))
        )

    return nu.let("", write)


def _wait(plane: nu.Str) -> nu.Nu:
    """The wait before a restart: the fixed delay, else the backoff, doubled after."""
    delay = _Arm.delay
    doubled = delay * 2.0
    backoff = nu.Delay(delay) >> delay.set(nu.If(doubled > BACKOFF_CAP, BACKOFF_CAP, doubled))
    fixed = supervised()[plane].delay

    def wait(given: nu.ObjectRef) -> nu.Nu:
        return nu.IfDo(nu.Float(given) >= 0.0, nu.Delay(given), backoff)

    return nu.let(atomic(fixed.fallback(-1.0)), wait)


def _pass(plane: nu.Str) -> nu.Nu:
    """One look at the plane's own run: start one, leave a live one, or act on how it ended.

    Level: what it does follows from the state alone, so a pass with
    nothing new does nothing.
    """
    row = supervised()[plane]
    runs = Space.exec.plane_runs
    up = row.policy.exists().and_(ops.plane.exists(plane))

    def look(held: nu.ObjectRef) -> nu.Nu:
        mine = nu.Str(held)
        opened = Space.info.opened_at.fallback(0.0)
        earlier = nu.If(runs.contains(mine), runs[mine].created_at < opened, True)
        fresh = nu.Bool(nu.If(mine == "", True, earlier))
        exit_ = runs[mine].exit.fallback("")
        always = row.policy.fallback("") == ALWAYS
        covered = (exit_ == EXIT_FAILED).or_((exit_ == EXIT_OK).and_(always))
        ended = Space.exec.indexes.live.plane_runs.contains(mine).not_().and_(covered)
        again = (
            nu.IfDo(atomic(exit_ == EXIT_OK), _Arm.delay.set(BACKOFF_START))
            >> _wait(plane)
            >> _start(plane, mine)
        )
        return nu.IfDo(atomic(fresh), _start(plane, mine), nu.IfDo(atomic(ended), again))

    return nu.IfDo(atomic(up), nu.let(atomic(row.run.fallback("")), look))


def _arm(plane: nu.Str) -> nu.Nu:
    """One supervised plane, kept up for as long as it is supervised.

    One subscription for the arm's life: its policy, its plane's live runs
    (a run leaves them in the commit that ends it) and its plane's row (a
    plane made later, or removed). The backoff lives across passes.
    """
    changes = nu.OnAny(
        atomic(supervised().on_child_change(plane)),
        atomic(ops.plane_run.on_live_change(plane=plane)),
        atomic(Space.planes.on_child_change(plane)),
    )
    held = restarting(nu.Reconcile(changes, _pass(plane), **_RECHECK), PLANE, plane)
    return nu.Frame(_Arm, held, delay=BACKOFF_START)


def driver() -> nu.Nu:
    """The supervisor's driver: :func:`_arm` per supervised plane, births and deaths included.

    Never returns. A raise outside an arm (reading the list) is reported and
    the driver runs again (``restarting``). Cost: per supervised plane, a
    few point reads a pass.
    """
    planes = supervised()
    listed = nu.If(planes.exists(), nu.list(planes.keys()), nu.Literal([]))
    arms = nu.ReconcileLatestEach(
        atomic(listed),
        atomic(planes.on_children_change()),
        lambda p: _arm(nu.Str(p)),
        **_RECHECK,
    )
    return restarting(arms, PLANE)
