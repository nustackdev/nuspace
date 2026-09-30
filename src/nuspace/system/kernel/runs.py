"""The run fold: one arm per plane run in ``running``, in the host, where the backends are.

An arm makes its plane run true, and ends it::

    backend start, started_at               a failure ends the run failed
    then race
      (a) watch termination_requested: the run and its live cell runs end
          killed, then the backend kills
      (b) fold over cells_running: each new cell run placed and run by the
          backend until its body ends; one leaving it has its body
          cancelled and the backend let go of what it held
      (c) cells_running empty: the run ends, its exit read off each cell's
          newest cell run (``latest``)
    finally: backend kill, whatever it still holds let go

A cell run's arm lives exactly as long as its body: the backend's run
returns when the body has ended, and says why when the worker died under
it, which ends the cell run ``failed`` here. With ``async`` one death fails
every cell run on the worker, with ``mp`` the one.

The arm never asks what backend it holds: every call goes through
:mod:`nuspace.system.backends` by the name on the record. Ending is a write
of ``terminated_at`` and ``exit`` plus a delete from the index, in one
commit; the fold sees the run leave ``running`` and cancels the arm.
"""

from __future__ import annotations

import nu
from nuspace.ops.utils import atomic, flag, fresh, text
from nuspace.shapes import EXIT_FAILED, EXIT_INTERRUPTED, EXIT_KILLED, EXIT_OK, Space
from nuspace.system import backends
from nuspace.system.backends import BackendRef, PlaceCell

from .body import end_cell_run
from .dispatch import RunCell
from .out import ErrorText
from .utils import Now, Ticking, park, snap, until


__all__ = ["RUN_ATTR", "end_run", "outcome", "run_arm", "run_fold"]


#: What the fold binds each plane run id under.
RUN_ATTR = "nuspace.kernel.run"

_kernel = Space.kernel

# Per arm names. Each fold arm runs on a context branch of its own, so one
# name serves every arm.
_BACKEND = "nuspace.kernel.backend"
_CELL_RUN = "nuspace.kernel.cell_run"
_PLACE = "nuspace.kernel.place"
_LOST = "nuspace.kernel.lost"
_ORPHAN = "Cell run lost its host arm"
_ERROR = "nuspace.kernel.error"
_WHY = "nuspace.kernel.why"


def outcome(run_id: nu.StrArg) -> nu.Nu:
    """A plane run's exit, read off each cell's newest cell run (``latest``). Bare read.

    ``failed`` if any failed, else ``ok`` if any returned, else
    ``interrupted`` if any was, else ``ok`` (a plane with no cells). A cell
    run superseded by a reload or a restart does not count. One pass over
    the run's cells, never its history, once, as it ends.
    """
    row = _kernel.runs[run_id]
    item = fresh("outcome")
    newest = row.cells[nu.ToStr(row.latest[nu.StrAttrRef(item)])]
    exits = nu.List(nu.Collect(nu.Map(nu.list(row.latest.keys()), text(newest.exit), key=item)))

    def some(exit_: str) -> nu.Nu:
        return exits.contains(nu.Str(exit_))

    return nu.If(
        some(EXIT_FAILED),
        nu.Str(EXIT_FAILED),
        nu.If(
            some(EXIT_OK),
            nu.Str(EXIT_OK),
            nu.If(some(EXIT_INTERRUPTED), nu.Str(EXIT_INTERRUPTED), nu.Str(EXIT_OK)),
        ),
    )


def end_run(run_id: nu.StrArg, exit_: nu.StrArg, error: nu.StrArg | None = None) -> nu.Nu:
    """A plane run's end: its live cell runs ended ``exit_``, then its own, out of ``running``. No bracket.

    Its live workers' records end in the same commit, ``killed`` with a
    killed run and ``ok`` otherwise (:func:`~nuspace.system.backends.released`).
    Written once: a run already ended keeps the end it has.
    """
    row = _kernel.runs[run_id]
    item = fresh("end_run")
    cells = nu.ForEachDo(
        nu.list(row.cells_running),
        end_cell_run(run_id, nu.StrAttrRef(item), exit_, error),
        item=item,
    )
    own = row.exit.set(exit_)
    if error is not None:
        own = own >> row.error.set(error)
    workers = nu.If(nu.Eq(exit_, nu.Str(EXIT_KILLED)), nu.Str(EXIT_KILLED), nu.Str(EXIT_OK))
    return (
        cells
        >> nu.IfDo(nu.Not(row.terminated_at.exists()), own >> row.terminated_at.set(Now()))
        >> backends.released(run_id, workers)
        >> nu.IfDo(_kernel.running.contains(run_id), _kernel.running.discard(run_id))
    )


def _end_if_done(run_id: nu.StrArg) -> nu.Nu:
    """End the run with its outcome when nothing of it runs. One commit.

    Checked inside the commit, so a ``cell_run`` landing first keeps it alive.
    """
    row = _kernel.runs[run_id]
    done = nu.And(_kernel.running.contains(run_id), nu.Eq(row.cells_running.len(), nu.Int(0)))
    return atomic(nu.IfDo(done, end_run(run_id, outcome(run_id))))


def _cell_arm(run_id: nu.StrArg, cell_run_id: nu.StrArg, backend: nu.StrArg) -> nu.Nu:
    """One live cell run: placed, then run by the backend until its body ends.

    The body writes its own end. A worker that died under it is the cell
    run and the worker ending ``failed`` with why, in one commit. A place or
    a run that raises (an unknown env, a worker gone) is the cell run
    failing. Cancelled, which is the cell run leaving ``cells_running``, the
    body is cancelled where it runs and the backend lets go of what it held
    for it.

    A cell run with a ``worker`` was placed by an arm that is gone (it
    raised past its own end), so nothing runs it: it ends ``failed``.
    """
    cr = _kernel.runs[run_id].cells[cell_run_id]
    place = nu.Let(
        _PLACE,
        PlaceCell(BackendRef(backend), run_id, cell_run_id),
        backends.placed(backend, run_id, cell_run_id, nu.ObjectAttrRef(_PLACE)),
    )
    why = nu.StrAttrRef(_LOST)
    lost = atomic(
        backends.lost(text(cr.worker), why) >> end_cell_run(run_id, cell_run_id, EXIT_FAILED, why)
    )
    run = nu.Let(
        _LOST, RunCell(backend, run_id, cell_run_id), nu.IfDo(nu.Ne(why, nu.Str("")), lost)
    )
    failed = nu.Let(
        _WHY,
        ErrorText(nu.ObjectAttrRef(_ERROR)),
        atomic(end_cell_run(run_id, cell_run_id, EXIT_FAILED, nu.StrAttrRef(_WHY))),
    )
    go = nu.IfDo(
        snap(nu.Not(cr.worker.exists())),
        nu.TryCatch(place >> run, catch=failed, error_key=_ERROR),
        atomic(end_cell_run(run_id, cell_run_id, EXIT_FAILED, _ORPHAN)),
    )
    return nu.TryCatch(go, finally_=backends.end_cell(backend, run_id, cell_run_id, EXIT_OK))


def _killed(run_id: nu.StrArg, backend: nu.StrArg) -> nu.Nu:
    """Wait for ``termination_requested``, then the run ends killed and the backend tears down.

    The end is written first, so the cell runs and workers read ``killed``
    before any worker goes: a body failing because its worker was killed
    finds its end written already.
    """
    asked = _kernel.runs[run_id].termination_requested
    return (
        until(flag(asked, False), asked.on_change())
        >> atomic(end_run(run_id, EXIT_KILLED))
        >> backends.kill(backend, run_id, EXIT_KILLED)
    )


def _cells(run_id: nu.StrArg, backend: nu.StrArg) -> nu.Nu:
    """:func:`_cell_arm` for every cell run in ``cells_running``, births and deaths included."""
    live = _kernel.runs[run_id].cells_running
    return nu.ForEachParReactive(
        snap(nu.list(live)),
        Ticking(snap(live.on_children_change())),
        _cell_arm(run_id, nu.StrAttrRef(_CELL_RUN), backend),
        _CELL_RUN,
    )


def _done(run_id: nu.StrArg) -> nu.Nu:
    """Wait for ``cells_running`` to empty, then end the run. Returns once it has ended."""
    live = _kernel.runs[run_id].cells_running
    return nu.WhileDo(
        snap(_kernel.running.contains(run_id)),
        until(nu.Eq(live.len(), nu.Int(0)), live.on_children_change()) >> _end_if_done(run_id),
    )


def run_arm(run_id: nu.StrArg) -> nu.Nu:
    """One plane run's whole life in the host. Ends only by the fold cancelling it."""
    row = _kernel.runs[run_id]
    backend = nu.StrAttrRef(_BACKEND)
    started = backends.start(backend, run_id) >> atomic(
        nu.IfDo(nu.Not(row.started_at.exists()), row.started_at.set(Now()))
    )
    failed = nu.Let(
        _WHY,
        nu.Str("Backend failed to start: ") + ErrorText(nu.ObjectAttrRef(_ERROR)),
        atomic(end_run(run_id, EXIT_FAILED, nu.StrAttrRef(_WHY))),
    )
    live = nu.Race(_killed(run_id, backend), _cells(run_id, backend), _done(run_id))
    life = nu.TryCatch(started, catch=failed, error_key=_ERROR) >> nu.IfDo(
        snap(_kernel.running.contains(run_id)), live
    )
    # Its workers go when the run is over, or the arm is cancelled: killed
    # when somebody asked for it, let go otherwise.
    let_go = nu.If(flag(row.termination_requested, False), nu.Str(EXIT_KILLED), nu.Str(EXIT_OK))
    return nu.Let(
        _BACKEND,
        snap(text(row.backend)),
        nu.TryCatch(life, finally_=backends.kill(backend, run_id, let_go)) >> park(),
    )


def run_fold() -> nu.Nu:
    """:func:`run_arm` for every plane run in ``running``, births and deaths included.

    The index must exist before this subscribes (reconcile makes it).
    """
    running = _kernel.running
    return nu.ForEachParReactive(
        snap(nu.list(running)),
        Ticking(snap(running.on_children_change())),
        run_arm(nu.StrAttrRef(RUN_ATTR)),
        RUN_ATTR,
    )
