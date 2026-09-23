"""reload: a live run whose cell's prog changes is replaced by a run of the new prog (D13).

One arm per live run. The arm reads the cell's prog once, waits for it to
change, then ups the cell again on the same worker, with the same envs and
the same ``by``, and only then downs the old run (D30: downing first would
leave the worker idle, and idle collection would take it in between). The
new run is live, so it gets an arm of its own and the next edit replaces it
in turn.

Skipped: runs already stopping, runs whose worker is gone or going, and
cells that no longer exist.
"""

from __future__ import annotations

import nu
from nuspace.ops import cell_exists, down, prog, up
from nuspace.ops.utils import or_else, text
from nuspace.shapes import STATUS_STOPPING, Space

from ..utils import moved, park, snap


__all__ = ["CELL", "PLANE", "SHIM", "program"]


#: The plane id, fixed (D31).
PLANE = "reload"

#: The one cell on the plane.
CELL = "main"

#: The cell's prog: the code lives here, the store holds this (D20).
SHIM = """\
from nuspace.system.services import reload


def out():
    return reload.program()
"""

_kernel = Space.kernel

_RUN = "nuspace.reload.run"
_PLANE = "nuspace.reload.plane"
_CELL = "nuspace.reload.cell"
_WORKER = "nuspace.reload.worker"
_SOURCE = "nuspace.reload.source"
_BY = "nuspace.reload.by"


def _replaceable(run_id: nu.StrAttrRef, plane: nu.Nu, cell: nu.Nu, worker: nu.Nu) -> nu.Nu:
    """Whether the run can be replaced where it is: live, not stopping, its worker living."""
    run = _kernel.runs[run_id]
    return nu.And(
        _kernel.live.contains(run_id),
        nu.Ne(text(run.status), nu.Str(STATUS_STOPPING)),
        _kernel.active.contains(worker),
        nu.Ne(text(_kernel.workers[worker].status), nu.Str(STATUS_STOPPING)),
        cell_exists(plane, cell),
    )


def _arm(run_id: nu.StrAttrRef) -> nu.Nu:
    """One live run: wait for its cell's prog to move, then replace it. Then parked."""
    run = _kernel.runs[run_id]
    plane, cell = nu.StrAttrRef(_PLANE), nu.StrAttrRef(_CELL)
    worker, by = nu.StrAttrRef(_WORKER), nu.StrAttrRef(_BY)
    source = Space.planes[plane].cells[cell].prog
    # Envs read inside up's own commit, never bound: a list read on a worker
    # is a reference into the host, and a bracket deep copies what is bound.
    envs = or_else(run.envs, [])
    replace = nu.IfDo(
        snap(_replaceable(run_id, plane, cell, worker)),
        up(plane, nu.List.of(cell), worker=worker, envs=envs, by=by) >> down(nu.List.of(run_id)),
    )
    watch = nu.Let(
        _SOURCE,
        snap(prog(plane, cell)),
        moved(source, nu.StrAttrRef(_SOURCE)) >> replace >> park(),
    )
    reads = (
        (_PLANE, text(run.plane)),
        (_CELL, text(run.cell)),
        (_WORKER, text(run.worker)),
        (_BY, text(run.by)),
    )
    for name, value in reversed(reads):
        watch = nu.Let(name, snap(value), watch)
    return watch


def program() -> nu.Nu:
    """One arm per live run, births and deaths included. Never returns."""
    live = _kernel.live
    return nu.ForEachParReactive(
        snap(nu.list(live.keys())),
        snap(live.on_children_change()),
        _arm(nu.StrAttrRef(_RUN)),
        _RUN,
    )
