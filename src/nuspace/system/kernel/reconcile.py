"""Reconcile: at open, everything the last open left running is dead.

A worker or run not ``dead`` in the store belongs to a process that is gone,
since workers die with the host. Marking them dead, ``exit: killed``, makes
the records true again before anything else reads them. It also makes the
kernel's containers real, since a fold subscribing to a container that is
not there never hears anything.
"""

from __future__ import annotations

import nu
from nuspace.ops.utils import atomic, fresh, text
from nuspace.shapes import EXIT_KILLED, STATUS_DEAD, Space

from .utils import Now


__all__ = ["reconcile"]


_kernel = Space.kernel


def _containers() -> nu.Nu:
    """Every kernel container made real, so a subscription on it resolves."""
    return (
        _kernel.workers.init(nu.Dict.create())
        >> _kernel.runs.init(nu.Dict.create())
        >> _kernel.live.init(nu.Dict.create())
        >> _kernel.active.init(nu.Dict.create())
    )


def reconcile() -> nu.Nu:
    """Mark every worker and run not dead as dead, clear ``live`` and ``active``. One commit.

    Runs get ``exit: killed`` (nobody asked them to stop), and both get
    ``ended``. Dead records are left as they are: they are history.
    """
    w_item, r_item = fresh("reconcile_w"), fresh("reconcile_r")
    worker = _kernel.workers[nu.StrAttrRef(w_item)]
    run = _kernel.runs[nu.StrAttrRef(r_item)]
    workers = nu.ForEachDo(
        nu.list(_kernel.workers.keys()),
        nu.IfDo(
            nu.Ne(text(worker.status), nu.Str(STATUS_DEAD)),
            worker.status.set(STATUS_DEAD) >> worker.ended.set(Now()),
        ),
        item=w_item,
    )
    runs = nu.ForEachDo(
        nu.list(_kernel.runs.keys()),
        nu.IfDo(
            nu.Ne(text(run.status), nu.Str(STATUS_DEAD)),
            run.status.set(STATUS_DEAD) >> run.exit.set(EXIT_KILLED) >> run.ended.set(Now()),
        ),
        item=r_item,
    )
    return atomic(
        _containers() >> workers >> runs >> _kernel.live.clear() >> _kernel.active.clear()
    )
