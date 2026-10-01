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
from nuspace.ops.utils import atomic
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

    def kill_worker(wid: nu.Attr) -> nu.Nu:
        worker = _kernel.workers[nu.Str(wid)]
        killed = worker.terminated_at.set(Now()) >> worker.exit.set(EXIT_KILLED)
        return nu.IfDo(worker.terminated_at.missing(), killed)

    return atomic(
        _containers()
        >> nu.ForEachDo(nu.list(_kernel.workers_running), kill_worker)
        >> nu.ForEachDo(nu.list(_kernel.running), lambda rid: end_run(nu.Str(rid), EXIT_KILLED))
        >> _kernel.workers_running.clear()
        >> _kernel.running.clear()
    )
