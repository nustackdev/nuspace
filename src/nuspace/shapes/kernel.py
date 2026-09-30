"""Kernel records: plane runs, their cell runs, the workers they run on, and what is live.

No status anywhere. A record logs intents (``*_requested``, written by ops)
and effects (``started_at``, ``terminated_at``, ``exit``, ``error``, written
by the kernel and the backends). Whether something is live is whether its id
is in an index: ``running`` for plane runs, ``cells_running`` for a plane
run's cell runs, ``workers_running`` for workers. Ending is a write of
``terminated_at`` plus a delete from the index. Nothing moves, nothing is
pruned, and nothing iterates ``runs`` or ``workers`` whole.
"""

from __future__ import annotations

import nu
import nustd.kv


__all__ = [
    "EXITS",
    "EXIT_FAILED",
    "EXIT_INTERRUPTED",
    "EXIT_KILLED",
    "EXIT_OK",
    "CellRun",
    "Kernel",
    "Run",
    "Worker",
]


#: It returned. For a plane run, no cell run of it failed. For a worker,
#: its backend let it go once the plane run was over.
EXIT_OK = "ok"

#: It raised, or its worker died under it. For a worker, it died by itself.
EXIT_FAILED = "failed"

#: Somebody asked, via ``cell_interrupt`` or ``plane_interrupt``.
EXIT_INTERRUPTED = "interrupted"

#: Torn down: ``plane_kill``, or reconcile at open.
EXIT_KILLED = "killed"

#: How a run or a worker ended. Tells a crash from a request.
EXITS = (EXIT_OK, EXIT_FAILED, EXIT_INTERRUPTED, EXIT_KILLED)


class CellRun(nu.Shape):
    """One execution of one cell, inside a plane run. Never mutated into another.

    A reload or a restart is a new cell run. ``version`` is the cell's
    version when this run was asked for, so a newer prog is told apart
    without reading source. ``by`` says who asked. ``worker`` is the id of
    the :class:`Worker` its backend put it on.

    ``out`` is ``[ts, stream, text]`` entries, a capped ring written whole by
    the run's own body.
    """

    cell = nustd.kv.StrRef.slot()
    version = nustd.kv.IntRef.slot()
    by = nustd.kv.StrRef.slot()
    worker = nustd.kv.StrRef.slot()
    started_at = nustd.kv.FloatRef.slot()
    interrupt_requested = nustd.kv.BoolRef.slot()
    terminated_at = nustd.kv.FloatRef.slot()
    exit = nustd.kv.StrRef.slot()
    error = nustd.kv.StrRef.slot()
    out = nustd.kv.PrimitiveListRef.slot()


class Run(nu.Shape):
    """One execution of a plane: the thing started, stopped and killed.

    ``backend`` is the plane's backend when the run was asked for. ``envs``
    is the env specs its cells run inside, each ``[name, *args]`` naming a
    factory registered at open: stored rather than the envs themselves
    because a function cannot be stored, and so anyone can run the plane
    the same way again.

    ``cells`` is every cell run it ever had, ``cells_running`` the live ones.
    ``latest`` maps each cell to its newest cell run, written with it, so a
    cell's current run is a point read and never a walk of ``cells``, which
    grows with every reload. The run ends once ``cells_running`` is empty,
    or on kill, its exit read off ``latest``. ``workers`` is every worker
    its backend ever gave it.
    """

    plane = nustd.kv.StrRef.slot()
    backend = nustd.kv.StrRef.slot()
    by = nustd.kv.StrRef.slot()
    envs = nustd.kv.PrimitiveListRef.slot()
    started_at = nustd.kv.FloatRef.slot()
    termination_requested = nustd.kv.BoolRef.slot()
    terminated_at = nustd.kv.FloatRef.slot()
    exit = nustd.kv.StrRef.slot()
    error = nustd.kv.StrRef.slot()
    cells = nustd.kv.DictRef.slot(CellRun)
    cells_running = nustd.kv.SetRef.slot(str)
    latest = nustd.kv.DictRef.slot(str)
    workers = nustd.kv.SetRef.slot(str)


class Worker(nu.Shape):
    """The executor unit a backend runs cells on: a process today, anything later.

    Written by its backend only, read by everybody. ``run`` is the plane run
    it belongs to. ``handle`` is the backend's own address for it, a str
    only the backend reads (the pool's id, for the process backends).
    ``exit`` is ``ok`` when its backend let it go, ``killed`` when the plane
    run was killed, ``failed`` when it died by itself (``error`` says how).
    """

    backend = nustd.kv.StrRef.slot()
    run = nustd.kv.StrRef.slot()
    handle = nustd.kv.StrRef.slot()
    started_at = nustd.kv.FloatRef.slot()
    terminated_at = nustd.kv.FloatRef.slot()
    exit = nustd.kv.StrRef.slot()
    error = nustd.kv.StrRef.slot()


class Kernel(nu.Shape):
    """Everything the kernel and the backends record.

    ``runs`` and ``workers`` are the source of truth, every one ever.
    ``running`` and ``workers_running`` are the live ids, so what is live is
    read in the time of what is live.
    """

    runs = nustd.kv.DictRef.slot(Run)
    running = nustd.kv.SetRef.slot(str)
    workers = nustd.kv.DictRef.slot(Worker)
    workers_running = nustd.kv.SetRef.slot(str)
