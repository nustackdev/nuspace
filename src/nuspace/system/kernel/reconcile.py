"""Reconcile: at open, everything the last open left live has ended, killed.

A plane run in ``running`` or a worker in ``workers_running`` belongs to a
process that is gone, since workers die with the host. Ending each
``killed``, its live cell runs with it, makes the records true again before
anything else reads them. Only the indexes are walked, never history. It
also makes the kernel's containers real, since a fold subscribing to a
container that is not there never hears anything.
"""

from __future__ import annotations

import nu
from nuspace.ops.utils import atomic, fresh
from nuspace.shapes import EXIT_KILLED, Space

from .runs import end_run
from .utils import Now


__all__ = ["reconcile"]


_kernel = Space.kernel


def _containers() -> nu.Nu:
    """Every kernel container made real, so a subscription on it resolves."""
    return (
        _kernel.runs.init(nu.Dict.create())
        >> _kernel.running.init(nu.Set.create())
        >> _kernel.workers.init(nu.Dict.create())
        >> _kernel.workers_running.init(nu.Set.create())
    )


def reconcile() -> nu.Nu:
    """End every live plane run and worker ``killed``, empty the indexes. One commit."""
    w_item, r_item = fresh("reconcile_w"), fresh("reconcile_r")
    worker = _kernel.workers[nu.StrAttrRef(w_item)]
    workers = nu.ForEachDo(
        nu.list(_kernel.workers_running),
        nu.IfDo(
            nu.Not(worker.terminated_at.exists()),
            worker.terminated_at.set(Now()) >> worker.exit.set(EXIT_KILLED),
        ),
        item=w_item,
    )
    runs = nu.ForEachDo(
        nu.list(_kernel.running), end_run(nu.StrAttrRef(r_item), EXIT_KILLED), item=r_item
    )
    return atomic(
        _containers()
        >> workers
        >> runs
        >> _kernel.workers_running.clear()
        >> _kernel.running.clear()
    )
