"""Kernel ops: ask for workers and runs, read what the kernel recorded.

The store is the transport (D1): these write records only. ``worker``
writes a worker in ``starting``, ``up`` writes runs in ``starting``,
``down`` and ``kill_worker`` move things to ``stopping``. The kernel, in
the host where the pool lives, sees the records and makes them true. So
every op here is safe from any process holding the store, a service on a
worker included.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
from nuspace.shapes import (
    KIND_LOCAL,
    STATUS_DEAD,
    STATUS_STARTING,
    STATUS_STOPPING,
    Space,
)

from .read import cell_exists, cells
from .utils import MintId, as_list, atomic, binding, fresh, or_else, text


if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from nu.domains.shape.refs.base import StructuredRef


__all__ = [
    "CELL_ATTR",
    "PLANE_ATTR",
    "RUN_ATTR",
    "active_workers",
    "down",
    "env",
    "kill_worker",
    "live_runs",
    "runs",
    "up",
    "up_plane",
    "worker",
    "workers",
]


#: The attr the kernel binds a run's plane id under, inside its body.
PLANE_ATTR = "nuspace.plane"

#: The attr the kernel binds a run's cell id under, inside its body.
CELL_ATTR = "nuspace.cell"

#: The attr the kernel binds a run's own id under, inside its body.
RUN_ATTR = "nuspace.run"

_kernel = Space.kernel


# --- workers -------------------------------------------------------------------


def worker(kind: nu.StrArg = KIND_LOCAL) -> nu.Nu:
    """Ask for a worker of ``kind``. The kernel takes a spare or makes one.

    Yields:
        The worker's store id, minted when this is evaluated.
    """

    def write(w: nu.StrAttrRef) -> nu.Nu:
        row = _kernel.workers[w]
        return (
            row.kind.set(kind)
            >> row.status.set(STATUS_STARTING)
            >> _kernel.active.set_item(w, nu.Bool(True))
        )

    return atomic(binding(MintId("w"), lambda name: write(nu.StrAttrRef(name)), tag="w"))


def kill_worker(worker_id: nu.StrArg) -> nu.Nu:
    """Ask the kernel to stop a worker. A no-op when it is missing, stopping or dead.

    Its runs go with it: the kernel marks them dead when the process exits.
    """
    row = _kernel.workers[worker_id]
    status = text(row.status)
    return atomic(
        nu.IfDo(
            nu.And(
                _kernel.workers.contains(worker_id),
                nu.Ne(status, nu.Str(STATUS_DEAD)),
                nu.Ne(status, nu.Str(STATUS_STOPPING)),
            ),
            row.status.set(STATUS_STOPPING),
        )
    )


# --- runs ----------------------------------------------------------------------


def env(name: str, *args: str) -> list[str]:
    """An env spec: the name a factory was registered under, then its args.

    Plain data, so it is stored on the run (``Run.envs``) and anyone can
    re-up the cell the same way.
    """
    return [name, *args]


def _envs(envs: Sequence[Sequence[str]] | nu.Nu) -> object:
    """Env specs as a value ``Run.envs`` stores whole."""
    if isinstance(envs, nu.Nu):
        return envs
    return nu.Literal([list(spec) for spec in envs])


def _up(
    plane_id: nu.StrArg,
    cell_ids: Sequence[nu.StrArg] | nu.Nu,
    worker_id: nu.StrArg,
    envs: Sequence[Sequence[str]] | nu.Nu,
    by: nu.StrArg,
) -> nu.Nu:
    """The body of :func:`up`, unbracketed. Yields the run ids."""
    specs = _envs(envs)

    def body(ids: str) -> nu.Nu:
        acc = nu.ListAttrRef(ids)
        cell, rid = fresh("up_cell"), fresh("up_run")
        cell_ref, rid_ref = nu.StrAttrRef(cell), nu.StrAttrRef(rid)
        row = _kernel.runs[rid_ref]
        write = (
            row.plane.set(plane_id)
            >> row.cell.set(cell_ref)
            >> row.worker.set(worker_id)
            >> row.by.set(by)
            >> row.envs.set(specs)
            >> row.status.set(STATUS_STARTING)
            >> _kernel.live.set_item(rid_ref, worker_id)
            >> nu.SetCmd(acc, nu.List(acc) + nu.List.of(rid_ref))
        )
        return nu.ForEachDo(
            as_list(cell_ids),
            nu.IfDo(cell_exists(plane_id, cell_ref), nu.Let(rid, MintId("r"), write)),
            item=cell,
        )

    return binding(nu.Literal([]), body, tag="up")


def up(
    plane_id: nu.StrArg,
    cell_ids: Sequence[nu.StrArg] | nu.Nu,
    *,
    worker: nu.StrArg,
    envs: Sequence[Sequence[str]] | nu.Nu = (),
    by: nu.StrArg = "",
) -> nu.Nu:
    """Ask for one run per cell, on ``worker``, inside ``envs``.

    Args:
        plane_id: the plane the cells are on.
        cell_ids: the cells, a python list or a term yielding one. Ids with
            no cell behind them are skipped.
        worker: the worker's store id, eg what :func:`worker` yielded.
        envs: env specs, outermost first, each ``env(name, *args)``.
        by: who asked, eg ``nav``.

    Yields:
        The new run ids, one per cell that exists, minted at evaluation.
    """
    return atomic(_up(plane_id, cell_ids, worker, envs, by))


def up_plane(
    plane_id: nu.StrArg,
    *,
    worker: nu.StrArg,
    envs: Sequence[Sequence[str]] | nu.Nu = (),
    by: nu.StrArg = "",
) -> nu.Nu:
    """:func:`up` on every cell of a plane, in order, on one worker."""
    return atomic(_up(plane_id, cells(plane_id), worker, envs, by))


def stop_runs(match: Callable[[StructuredRef], nu.Nu]) -> nu.Nu:
    """Ask every live run ``match(run)`` holds for to stop. No bracket.

    For ops that take away what runs belong to (a plane, a cell).
    """
    item = fresh("stop")
    row = _kernel.runs[nu.StrAttrRef(item)]
    return nu.ForEachDo(
        nu.list(_kernel.live.keys()),
        nu.IfDo(
            nu.And(match(row), nu.Ne(text(row.status), nu.Str(STATUS_STOPPING))),
            row.status.set(STATUS_STOPPING),
        ),
        item=item,
    )


def down(run_ids: Sequence[nu.StrArg] | nu.Nu) -> nu.Nu:
    """Ask runs to stop. Runs not live (dead, or never made) are skipped.

    The kernel does the stopping: a run's body watches its own status.
    """
    item = fresh("down")
    rid = nu.StrAttrRef(item)
    status = _kernel.runs[rid].status
    return atomic(
        nu.ForEachDo(
            as_list(run_ids),
            nu.IfDo(
                nu.And(_kernel.live.contains(rid), nu.Ne(text(status), nu.Str(STATUS_STOPPING))),
                status.set(STATUS_STOPPING),
            ),
            item=item,
        )
    )


# --- reads ---------------------------------------------------------------------


def _run_row(rid: nu.StrAttrRef) -> nu.Nu:
    row = _kernel.runs[rid]
    return nu.Dict.of(
        id=rid,
        plane=text(row.plane),
        cell=text(row.cell),
        worker=text(row.worker),
        by=text(row.by),
        envs=or_else(row.envs, []),
        status=text(row.status),
        exit=text(row.exit),
        error=text(row.error),
        started=or_else(row.started, None),
        ended=or_else(row.ended, None),
        out=or_else(row.out, []),
    )


def runs(
    *,
    plane: nu.StrArg | None = None,
    cell: nu.StrArg | None = None,
    status: nu.StrArg | None = None,
    worker: nu.StrArg | None = None,
) -> nu.Nu:
    """Every run recorded, dead ones included, as dicts with their ``id``.

    Each argument given narrows it. Minted ids sort by creation, so this is
    oldest first: a cell's history is ``runs(plane=p, cell=c)``.
    """
    item = fresh("runs")
    rid = nu.StrAttrRef(item)
    row = _kernel.runs[rid]
    wanted = [
        nu.Eq(text(ref), value)
        for ref, value in (
            (row.plane, plane),
            (row.cell, cell),
            (row.status, status),
            (row.worker, worker),
        )
        if value is not None
    ]
    ids: nu.Nu = nu.list(_kernel.runs.keys())
    if wanted:
        cond = wanted[0] if len(wanted) == 1 else nu.And(*wanted)
        ids = nu.Filter(ids, cond, key=item)
    return nu.Collect(nu.Map(ids, _run_row(rid), key=item))


def live_runs(worker: nu.StrArg | None = None) -> nu.Nu:
    """Ids of runs not dead, on ``worker`` when given."""
    ids = nu.list(_kernel.live.keys())
    if worker is None:
        return ids
    item = fresh("live")
    return nu.List(
        nu.Collect(nu.Filter(ids, nu.Eq(_kernel.live[nu.StrAttrRef(item)], worker), key=item))
    )


def workers() -> nu.Nu:
    """Every worker recorded, dead ones included, as dicts with their ``id``."""
    item = fresh("workers")
    wid = nu.StrAttrRef(item)
    row = _kernel.workers[wid]
    return nu.Collect(
        nu.Map(
            nu.list(_kernel.workers.keys()),
            nu.Dict.of(
                id=wid,
                kind=text(row.kind),
                wid=or_else(row.wid, None),
                status=text(row.status),
                error=text(row.error),
                started=or_else(row.started, None),
                ended=or_else(row.ended, None),
            ),
            key=item,
        )
    )


def active_workers() -> nu.Nu:
    """Ids of workers not dead."""
    return nu.list(_kernel.active.keys())
