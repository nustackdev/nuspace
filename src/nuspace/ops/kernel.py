"""Kernel ops: run planes, interrupt and kill them, run and interrupt their cells.

The store is the transport (D1): these write intents only. ``plane_run``
and ``cell_run`` write new records into the live indexes, the interrupts
set ``interrupt_requested``, ``plane_kill`` sets ``termination_requested``.
The kernel, in the host where the backends live, sees the records and makes
them true, and it and the backends write every effect. So every op here is
safe from any process holding the store, a service on a worker included.

Every op is O(1) or O(k), k being what is live of what it asks about: a
plane's live runs are its ``planes_running``, a run's live cell runs its
``cells_running``, its live workers its ``workers_running``, never ``runs``
nor all of ``running``. A cell's newest cell run in a plane run is a point
read of the run's ``latest`` (:func:`latest`), never a walk of its
``cells``, which grows with every reload.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nustd.kv
from nuspace.shapes import Space

from .read import cell_plane, cells, plane_exists
from .utils import MintId, atomic


if TYPE_CHECKING:
    from collections.abc import Callable, Sequence


__all__ = [
    "STOP_GRACE",
    "Here",
    "add_cell_run",
    "add_plane_run",
    "cell_interrupt",
    "cell_run",
    "cell_runs",
    "env",
    "interrupt",
    "interrupt_cell",
    "kill",
    "latest",
    "live_runs_of",
    "off_running",
    "plane_interrupt",
    "plane_kill",
    "plane_run",
    "plane_stop",
    "run",
    "runs",
    "workers",
]


class Here(nu.Shape):
    """Where a cell run's body runs: the ids the kernel holds for it in a frame.

    The kernel opens a frame over this Shape around every cell run's body,
    so a program and its envs read these, eg ``Here.plane``, and never set
    them.
    """

    plane = nu.StrRef.slot()
    cell = nu.StrRef.slot()
    run = nu.StrRef.slot()
    cell_run = nu.StrRef.slot()


#: How long ``plane_stop`` waits after interrupting before it kills, in seconds.
STOP_GRACE = 10.0

_kernel = Space.kernel


def _snap(term: nu.Nu) -> nu.Nu:
    return nustd.kv.Snapshot(term, scope=Space)


# --- Running -------------------------------------------------------------------


def env(name: str, *args: str) -> list[str]:
    """An env spec: the name a factory was registered under, then its args.

    Plain data, so it is stored on the run (``Run.envs``) and anyone can run
    the plane the same way again.
    """
    return [name, *args]


def _envs(envs: Sequence[Sequence[str]] | nu.Nu) -> object:
    """Env specs as a value ``Run.envs`` stores whole."""
    if isinstance(envs, nu.Nu):
        return envs
    return nu.Literal([list(spec) for spec in envs])


def _add_cell_run(
    run_id: nu.StrArg, cell_id: nu.StrArg, cell_run_id: nu.StrArg, by: nu.StrArg
) -> nu.Nu:
    """One cell run written into a plane run, its ``cells_running`` and ``latest``. No bracket."""
    row = _kernel.runs[run_id]
    cr = row.cells[cell_run_id]
    return (
        cr.cell.set(cell_id)
        >> cr.version.set(Space.cells[cell_id].version.fallback(0))
        >> cr.by.set(by)
        >> cr.interrupt_requested.set(False)
        >> row.cells_running.add(cell_run_id)
        >> row.latest.set_item(cell_id, cell_run_id)
    )


def add_plane_run(
    run_id: nu.StrArg,
    plane_id: nu.StrArg,
    *,
    by: nu.StrArg = "",
    envs: Sequence[Sequence[str]] | nu.Nu = (),
) -> nu.Nu:
    """A plane run written under ``run_id``, a cell run per cell, into the live indexes. No bracket.

    For ops and services that write a run and their own record of it in one
    commit. Nothing is written when the plane is missing.
    """
    row = _kernel.runs[run_id]
    writes = (
        row.plane.set(plane_id)
        >> row.backend.set(Space.planes[plane_id].props.backend.fallback(""))
        >> row.by.set(by)
        >> row.envs.set(_envs(envs))
        >> row.termination_requested.set(False)
        >> row.cells.init({})
        >> row.cells_running.init(set())
        >> row.latest.init({})
        >> row.workers.init(set())
        >> nu.ForEachDo(
            cells(plane_id),
            lambda cell: nu.let(
                MintId("cr"),
                lambda cr: _add_cell_run(run_id, nu.Str(cell), nu.Str(cr), by),
            ),
        )
        >> _kernel.running.add(run_id)
        >> _kernel.planes_running[plane_id].runs.add(run_id)
    )
    return nu.IfDo(plane_exists(plane_id), writes)


def plane_run(
    plane_id: nu.StrArg,
    *,
    by: nu.StrArg = "",
    envs: Sequence[Sequence[str]] | nu.Nu = (),
    into: nu.Ref | None = None,
) -> nu.Nu:
    """Run a plane: a new plane run with a cell run per cell, in order. One commit.

    The run takes the plane's ``backend`` prop as it is now. A plane with no
    cells makes a run the kernel ends at once. A plane with no backend makes
    a run the kernel ends failed, the error saying so: there is no default.

    Args:
        plane_id: The plane.
        by: Who asked, eg ``nav``.
        envs: Env specs its cells run inside, outermost first, each
            ``env(name, *args)``.
        into: Set to the run id in the commit, ``""`` when the plane is
            missing, for a caller that needs it: the record does not say
            which run this call made. A retried commit sets it again, so it
            names the run that landed.
    """

    def write(rid: nu.ObjectRef) -> nu.Nu:
        made = add_plane_run(nu.Str(rid), plane_id, by=by, envs=envs)
        if into is None:
            return made
        return made >> into.set(nu.If(plane_exists(plane_id), nu.Str(rid), ""))

    return atomic(nu.let(MintId("r"), write))


def add_cell_run(
    run_id: nu.StrArg, cell_id: nu.StrArg, cell_run_id: nu.StrArg, by: nu.StrArg = ""
) -> nu.Nu:
    """A cell run written into a live plane run, under ``cell_run_id``. No bracket.

    Nothing is written when the plane run is not live or the cell is not on
    its plane.
    """
    on = cell_plane(cell_id) == _kernel.runs[run_id].plane.fallback("")
    live = _kernel.running.contains(run_id).and_(on)
    return nu.IfDo(live, _add_cell_run(run_id, cell_id, cell_run_id, by))


def cell_run(run_id: nu.StrArg, cell_id: nu.StrArg, *, by: nu.StrArg = "") -> nu.Nu:
    """Run a cell inside a live plane run: a new cell run, beside any other of it. One commit.

    The new cell run is the cell's :func:`latest` in the run, where a caller
    reads it. Nothing is written when the plane run is not live or the cell
    is not on its plane.
    """
    return atomic(nu.let(MintId("cr"), lambda cr: add_cell_run(run_id, cell_id, nu.Str(cr), by)))


def interrupt(run_id: nu.StrArg, cell_run_id: nu.StrArg) -> nu.Nu:
    """Ask a live cell run to stop, unless it was asked already. No bracket."""
    ask = _kernel.runs[run_id].cells[cell_run_id].interrupt_requested
    live = _kernel.runs[run_id].cells_running.contains(cell_run_id)
    return nu.IfDo(live.and_(ask.fallback(False).not_()), ask.set(True))


def cell_interrupt(run_id: nu.StrArg, cell_run_id: nu.StrArg) -> nu.Nu:
    """Ask a cell run to stop. A no-op when it is not live. One commit.

    Cooperative: its body watches ``interrupt_requested`` and ends itself
    ``interrupted``. There is no cell kill: a backend may not be able to
    kill one cell alone, so kill is a plane op.
    """
    return atomic(interrupt(run_id, cell_run_id))


def plane_interrupt(run_id: nu.StrArg) -> nu.Nu:
    """Ask every live cell run of a plane run to stop. One commit.

    Once they have, ``cells_running`` is empty and the run ends.
    """
    live = nu.list(_kernel.runs[run_id].cells_running)
    return atomic(nu.ForEachDo(live, lambda cr: interrupt(run_id, nu.Str(cr))))


def kill(run_id: nu.StrArg) -> nu.Nu:
    """Ask the kernel to tear a live plane run down. No bracket."""
    ask = _kernel.runs[run_id].termination_requested
    live = _kernel.running.contains(run_id)
    return nu.IfDo(live.and_(ask.fallback(False).not_()), ask.set(True))


def plane_kill(run_id: nu.StrArg) -> nu.Nu:
    """Tear a plane run down: its backend kills whatever runs it. One commit.

    Not cooperative: its live cell runs end ``killed`` without a say. A
    no-op when the run is not live.
    """
    return atomic(kill(run_id))


def _until_ended(run_id: nu.StrArg) -> nu.Nu:
    """Wait until a plane run is out of ``running``. Returns at once if it is.

    Woken by its plane's live runs, which it leaves in the same commit.
    """
    live = _kernel.planes_running[_kernel.runs[run_id].plane.fallback("")].runs
    return nu.WaitReactive(
        _snap(live.on_children_change()), _snap(_kernel.running.contains(run_id).not_())
    )


def plane_stop(run_id: nu.StrArg, grace: nu.FloatArg = STOP_GRACE) -> nu.Nu:
    """Interrupt a plane run, then kill it if it is still running after ``grace`` seconds.

    Two intents, written as they fall due. Returns once the run has ended,
    or once the kill is asked for: a caller waits ``grace`` at most.
    """
    return plane_interrupt(run_id) >> nu.Timeout(
        grace, _until_ended(run_id), on_timeout=plane_kill(run_id)
    )


# --- Unbracketed parts, for ops that take away what runs belong to ----------------------


def off_running(run_id: nu.StrArg) -> nu.Nu:
    """A plane run out of ``running`` and out of its plane's live runs. No bracket.

    The one way out of both, so they never disagree. A plane whose last
    live run this was leaves ``planes_running``.
    """
    plane = _kernel.runs[run_id].plane.fallback("")
    live = _kernel.planes_running[plane].runs
    last = nu.IfDo(live.len() == 0, _kernel.planes_running.del_item(plane))
    mine = nu.IfDo(
        _kernel.planes_running.contains(plane), live.remove(run_id, missing_ok=True) >> last
    )
    return mine >> _kernel.running.remove(run_id, missing_ok=True)


def live_runs_of(plane_id: nu.StrArg, body: Callable[[nu.Str], nu.Nu]) -> nu.Nu:
    """``body(run_id)`` for every live plane run of the plane. No bracket."""
    live = nu.list(_kernel.planes_running[plane_id].runs)
    return nu.ForEachDo(live, lambda rid: body(nu.Str(rid)))


def interrupt_cell(cell_id: nu.StrArg) -> nu.Nu:
    """Ask every live cell run of a cell, in any live run of its plane, to stop. No bracket."""

    def one(rid: nu.Str, cr: nu.Str) -> nu.Nu:
        same = _kernel.runs[rid].cells[cr].cell.fallback("") == cell_id
        return nu.IfDo(same, interrupt(rid, cr))

    return live_runs_of(
        cell_plane(cell_id),
        lambda rid: nu.ForEachDo(
            nu.list(_kernel.runs[rid].cells_running), lambda cr: one(rid, nu.Str(cr))
        ),
    )


# --- Reads ---------------------------------------------------------------------


def latest(run_id: nu.StrArg, cell_id: nu.StrArg) -> nu.Str:
    """A cell's newest cell run in a plane run, live or ended, ``""`` when it has none. Bare read.

    A point read of the run's ``latest``: O(1) however many times the cell
    was reloaded or restarted in it.
    """
    return _kernel.runs[run_id].latest.get_item(cell_id, "")


def cell_runs(run_id: nu.StrArg, *, live: bool = False) -> nu.List:
    """A plane run's cell runs as dicts with their ``id``, oldest first. Bare read.

    Every one it ever had, or with ``live`` only those in ``cells_running``.
    Minted ids sort by creation, so sorted is oldest first.
    """
    run = _kernel.runs[run_id]

    def row(cr: nu.Attr) -> nu.Dict:
        cell_run = run.cells[nu.Str(cr)]
        return nu.Dict.of(
            id=cr,
            cell=cell_run.cell.fallback(""),
            version=cell_run.version.fallback(0),
            by=cell_run.by.fallback(""),
            worker=cell_run.worker.fallback(""),
            started_at=cell_run.started_at.fallback(None),
            interrupt_requested=cell_run.interrupt_requested.fallback(False),
            terminated_at=cell_run.terminated_at.fallback(None),
            exit=cell_run.exit.fallback(""),
            error=cell_run.error.fallback(""),
            out=cell_run.out.fallback([]),
        )

    ids = nu.sorted(run.cells_running) if live else nu.list(run.cells.keys())
    return ids.iter().map(row).to_list()


def _run_row(rid: nu.StrArg, *, whole: bool = False) -> nu.Dict:
    """A plane run as a dict. ``workers`` is every worker it had when ``whole``, else its live ones."""
    row = _kernel.runs[rid]
    return nu.Dict.of(
        id=rid,
        plane=row.plane.fallback(""),
        backend=row.backend.fallback(""),
        by=row.by.fallback(""),
        envs=row.envs.fallback([]),
        started_at=row.started_at.fallback(None),
        termination_requested=row.termination_requested.fallback(False),
        terminated_at=row.terminated_at.fallback(None),
        exit=row.exit.fallback(""),
        error=row.error.fallback(""),
        cells_running=nu.sorted(row.cells_running),
        latest=row.latest.extract(),
        workers=nu.sorted(row.workers if whole else row.workers_running),
    )


def runs(plane: nu.StrArg | None = None) -> nu.List:
    """The live plane runs as dicts with their ``id``, oldest first. Bare read.

    Live is ``running``, so this reads in the time of what is live, its
    ``workers`` the live ones. With ``plane``, that plane's live runs only.
    A run's cell runs are :func:`cell_runs`; an ended run is read by id with
    :func:`run`.
    """
    live = _kernel.running if plane is None else _kernel.planes_running[plane].runs
    return nu.sorted(live).iter().map(lambda rid: _run_row(nu.Str(rid))).to_list()


def run(run_id: nu.StrArg) -> nu.Dict:
    """One plane run by id, live or ended, whole: every cell run under ``cells``, every worker. Bare read.

    The one read that walks a run's history, for inspecting it: O(what the
    run ever had). Nothing that runs on repeat reads it.
    """
    return _run_row(run_id, whole=True).merge(nu.Dict.of(cells=cell_runs(run_id)))


def workers() -> nu.List:
    """The live workers as dicts with their ``id``, oldest first. Bare read.

    ``handle`` is the backend's own, not for reading into.
    """

    def row(wid: nu.Attr) -> nu.Dict:
        worker = _kernel.workers[nu.Str(wid)]
        return nu.Dict.of(
            id=wid,
            backend=worker.backend.fallback(""),
            run=worker.run.fallback(""),
            plane=_kernel.runs[worker.run.fallback("")].plane.fallback(""),
            handle=worker.handle.fallback(""),
            started_at=worker.started_at.fallback(None),
        )

    return nu.sorted(_kernel.workers_running).iter().map(row).to_list()
