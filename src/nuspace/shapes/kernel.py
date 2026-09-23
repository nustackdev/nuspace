"""Kernel records: workers, runs, and the index of what is live.

The kernel is their only writer. Services and the shell read them, and call
ops to ask for changes (the ops write requests, the kernel reconciles).
"""

from __future__ import annotations

import nu
import nustd.kv


__all__ = [
    "EXITS",
    "EXIT_FAILED",
    "EXIT_KILLED",
    "EXIT_OK",
    "EXIT_STOPPED",
    "KINDS",
    "KIND_DOCKER",
    "KIND_LOCAL",
    "KIND_REMOTE",
    "STATUSES",
    "STATUS_DEAD",
    "STATUS_STARTING",
    "STATUS_STOPPING",
    "STATUS_UP",
    "Kernel",
    "Run",
    "Worker",
]


#: Asked for, not running yet.
STATUS_STARTING = "starting"

#: Running.
STATUS_UP = "up"

#: Asked to stop. A run's body watches for this and exits on its own.
STATUS_STOPPING = "stopping"

#: Gone. Kept as history, never revived: a restart is a new run.
STATUS_DEAD = "dead"

#: A run's or a worker's lifecycle, in order. Only the kernel moves it.
STATUSES = (STATUS_STARTING, STATUS_UP, STATUS_STOPPING, STATUS_DEAD)

#: The program returned.
EXIT_OK = "ok"

#: The program raised, or its worker died under it.
EXIT_FAILED = "failed"

#: Somebody asked, via ``down``.
EXIT_STOPPED = "stopped"

#: Nobody asked the run: reconcile at open, or its worker was killed.
EXIT_KILLED = "killed"

#: How a run ended. Tells a crash from a request.
EXITS = (EXIT_OK, EXIT_FAILED, EXIT_STOPPED, EXIT_KILLED)

#: A python process from the pool on this machine.
KIND_LOCAL = "local"

#: Reserved.
KIND_DOCKER = "docker"

#: Reserved.
KIND_REMOTE = "remote"

#: How a worker is made. Only ``local`` exists for now.
KINDS = (KIND_LOCAL, KIND_DOCKER, KIND_REMOTE)


class Worker(nu.Shape):
    """Where runs execute. Keyed by a minted id, not the pool's.

    ``wid`` is the pool's own id for the process. Pool ids are process local
    ints, so the store keys workers by an id the kernel mints and keeps the
    pool's here.

    ``error`` says why it died when nobody asked it to: a crash, or a kind
    the kernel cannot make.
    """

    kind = nustd.kv.StrRef.slot()
    wid = nustd.kv.IntRef.slot()
    status = nustd.kv.StrRef.slot()
    error = nustd.kv.StrRef.slot()
    started = nustd.kv.FloatRef.slot()
    ended = nustd.kv.FloatRef.slot()


class Run(nu.Shape):
    """One execution of one cell, on one worker. Never mutated into another.

    A restart or a prog edit is a new run, so a cell's history is its runs
    by ``started``. ``worker`` is the store id of a :class:`Worker`. ``by``
    says who asked, eg ``nav`` or ``init``.

    ``envs`` is the env specs the run was built with, each ``[name, *args]``
    naming a factory registered at open. Stored rather than the envs
    themselves because a function cannot be stored, and so anyone can re-up
    the cell the same way.

    ``out`` is ``[ts, stream, text]`` entries, a capped ring. ``envs`` and
    ``out`` are whole value lists: read back as plain python lists, and
    rewritten whole, which is fine for a spec written once and a small ring.
    """

    plane = nustd.kv.StrRef.slot()
    cell = nustd.kv.StrRef.slot()
    worker = nustd.kv.StrRef.slot()
    by = nustd.kv.StrRef.slot()
    envs = nustd.kv.PrimitiveListRef.slot()
    status = nustd.kv.StrRef.slot()
    exit = nustd.kv.StrRef.slot()
    error = nustd.kv.StrRef.slot()
    started = nustd.kv.FloatRef.slot()
    ended = nustd.kv.FloatRef.slot()
    out = nustd.kv.PrimitiveListRef.slot()


class Kernel(nu.Shape):
    """Everything the kernel records.

    ``live`` is ``run id -> worker id`` for every run not dead: what is
    running, and what runs on a worker, without scanning history.

    ``active`` is ``worker id -> True`` for every worker not dead, so the
    kernel's worker fold iterates the living rather than the history.
    """

    workers = nustd.kv.ShapesDictRef.slot(Worker)
    runs = nustd.kv.ShapesDictRef.slot(Run)
    live = nustd.kv.DictRef.slot(str)
    active = nustd.kv.DictRef.slot(bool)
