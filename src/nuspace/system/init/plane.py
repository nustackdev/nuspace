"""The init plane: starts the planes on its boot list when the space opens.

One cell, :data:`CELL`, runs :func:`driver`. The host asks for init's own
plane run at open (``nuspace.system.start``); init asks for the rest. A
plane on the boot list (:class:`~.shapes.Boot`) gets one plane run ``by``
init in every open, unless it already ran in this open:

    on the list, there, not supervised, not live, no run since the open   plane_run.add(by="init")
    anything else                                                         left alone

A supervised plane is the supervisor's: it runs one at every open itself,
so init leaves it alone and a plane booted and supervised gets one run, not
two.

"Since the open" is a run created at or after ``Space.info.opened_at``,
which the host stamps before the drivers start. So a pass is idempotent:
a booted plane whose run ended stays down until the next open (bringing
it back is the supervisor's job), and booting a plane mid open runs it
once, now.

The driver is a level flow on the boot list with the standard re-checks:
a missed notification is a late boot, never a lost one. Each plane's check
and its run are one commit. A raise is caught per plane and reported, so
one bad entry never stops the others; one outside them restarts the
driver. Cost: O(boot list) per pass.
"""

from __future__ import annotations

import nu
from nuspace import ops
from nuspace.ops.brackets import atomic
from nuspace.shapes import Space
from nuspace.utils import keys_of
from nuspace.utils.policies import report, restarting

from .. import supervisor
from .shapes import PLANE, boot_list


__all__ = ["BACKEND", "BOOTED", "BY", "CELL", "PROG", "driver"]


#: Its one cell's id, fixed.
CELL = "init_main"

#: What its runs execute on.
BACKEND = "mp"

#: What the plane runs init asks for are recorded as ``by``.
BY = "init"

#: What the boot list starts as, the first time the system planes are made.
BOOTED = ("supervisor", "reload", "reactions")

#: The cell's prog: the driver lives here, the store holds this.
PROG = """\
from nuspace.system.init import plane


def out():
    return plane.driver()
"""


def _supervised(plane: nu.Str) -> nu.Bool:
    """Whether the supervisor keeps the plane up, so its runs are the supervisor's. One point read.

    The supervisor plane itself is never skipped: init is what brings it up.
    """
    policy = supervisor.supervised()[plane].policy
    return policy.exists().and_(plane != supervisor.PLANE)


def _due(plane: nu.Str) -> nu.Bool:
    """Whether a listed plane is to be run now. A read: about 7 point reads.

    It is there, not removed, not supervised, has no live plane run, and its
    newest plane run (if any) is older than this open.
    """
    runs = Space.exec.indexes.history.plane_to_plane_runs[plane].runs
    opened = Space.info.opened_at.fallback(0.0)
    newest = Space.exec.plane_runs[runs.last()].created_at
    ran = nu.Bool(nu.If(runs.exists(), newest >= opened, False))
    return (
        ops.plane.exists(plane)
        .and_(_supervised(plane).not_())
        .and_(ops.plane_run.any_live(plane).not_())
        .and_(ran.not_())
    )


def _up(plane: nu.Str) -> nu.Nu:
    """One listed plane run if it is due, check and run in one commit. A raise is reported."""
    up = atomic(nu.IfDo(_due(plane), ops.plane_run.add(plane, by=BY)))
    return nu.TryCatch(up, catch=lambda err: report(PLANE, plane, err))


def driver() -> nu.Nu:
    """The init driver: every due plane on the boot list run, at open and on every list change.

    Never returns. Bracketed per step: each plane is its own commit. A
    raise outside a plane's step (reading the list) is reported and the
    driver runs again (``restarting``).
    """
    planes = boot_list()
    listed = keys_of(planes)
    one_pass = nu.ForEachDo(atomic(listed), lambda p: _up(nu.Str(p)))
    flow = nu.Reconcile(
        atomic(planes.on_children_change()),
        one_pass,
        after=nu.RECHECK_AFTER,
        every=nu.RECHECK_EVERY,
    )
    return restarting(flow, PLANE)
