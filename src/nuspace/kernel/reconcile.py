"""Reconcile: at open, everything the last open left live has ended, killed.

A plane run in ``running`` or a worker in ``workers_running`` belongs to a
process that is gone, since workers die with the host. Ending each
``killed``, its live cell runs with it, makes the records true again before
anything else reads them, the narrower indexes (by plane, by run) emptied
with them. Only the indexes are walked, never history. It runs first, so it
also makes both stores' fixed containers real up front, the kernel's
included: every read after it (the walks here, ``running.contains``, a
run's lookups, the planes listed) finds a container, never an absent one.
"""

from __future__ import annotations

import nu
from nuspace.ops import init_stores
from nuspace.ops.utils import atomic
from nuspace.shapes import EXIT_KILLED, Space
from nuspace.system import backends

from .runs import end_run


__all__ = ["reconcile"]


_kernel = Space.kernel


def reconcile() -> nu.Nu:
    """The stores' containers made, then every live run and worker ended ``killed``, indexes emptied."""
    return init_stores() >> atomic(
        nu.ForEachDo(
            nu.list(_kernel.workers_running), lambda wid: backends.ended(nu.Str(wid), EXIT_KILLED)
        )
        >> nu.ForEachDo(nu.list(_kernel.running), lambda rid: end_run(nu.Str(rid), EXIT_KILLED))
        >> _kernel.workers_running.clear()
        >> _kernel.running.clear()
        >> _kernel.planes_running.clear()
    )
