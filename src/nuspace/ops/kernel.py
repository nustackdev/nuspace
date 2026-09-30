"""Kernel ops: run planes, interrupt and kill them, run and interrupt their cells.

The store is the transport (D1): these write intents only. ``plane_run``
and ``cell_run`` write new records into the live indexes, the interrupts
set ``interrupt_requested``, ``plane_kill`` sets ``termination_requested``.
The kernel, in the host where the backends live, sees the records and makes
them true, and it and the backends write every effect. So every op here is
safe from any process holding the store, a service on a worker included.

Every op is O(1) or O(k), k being what is live: they walk ``running`` and a
run's ``cells_running``, never ``runs``. A cell's newest cell run in a plane
run is a point read of the run's ``latest`` (:func:`latest`), never a walk of
its ``cells``, which grows with every reload.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nustd.kv
from nuspace.shapes import Space

from .read import cell_exists, cells, plane_exists
from .utils import MintId, atomic, binding, flag, fresh, or_else, text


if TYPE_CHECKING:
    from collections.abc import Callable, Sequence


__all__ = [
    "CELL_ATTR",
    "CELL_RUN_ATTR",
    "PLANE_ATTR",
    "RUN_ATTR",
    "STOP_GRACE",
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
    "plane_interrupt",
    "plane_kill",
    "plane_run",
    "plane_stop",
    "run",
    "runs",
    "workers",
]


#: The attr the kernel binds a cell run's plane id under, inside its body.
PLANE_ATTR = "nuspace.plane"

#: The attr the kernel binds a cell run's cell id under, inside its body.
CELL_ATTR = "nuspace.cell"

#: The attr the kernel binds the plane run's id under, inside a cell run's body.
RUN_ATTR = "nuspace.run"

#: The attr the kernel binds the cell run's own id under, inside its body.
CELL_RUN_ATTR = "nuspace.cell_run"

#: How long ``plane_stop`` waits after interrupting before it kills, in seconds.
STOP_GRACE = 10.0

#: How long a wait trusts its subscription before reading again.
_WATCH = 1.0

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


def _version(plane_id: nu.StrArg, cell_id: nu.StrArg) -> nu.Nu:
    """A cell's version, 0 where it was never written."""
    ref = Space.planes[plane_id].cells[cell_id].version
    return nu.If(ref.exists(), nu.ToInt(ref), nu.Int(0))


def _add_cell_run(
    run_id: nu.StrArg,
    plane_id: nu.StrArg,
    cell_id: nu.StrArg,
    cell_run_id: nu.StrArg,
    by: nu.StrArg,
) -> nu.Nu:
    """One cell run written into a plane run, its ``cells_running`` and ``latest``. No bracket."""
    row = _kernel.runs[run_id]
    cr = row.cells[cell_run_id]
    return (
        cr.cell.set(cell_id)
        >> cr.version.set(_version(plane_id, cell_id))
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
    """A plane run written under ``run_id``, a cell run per cell, into ``running``. No bracket.

    For ops and services that write a run and their own record of it in one
    commit. Nothing is written when the plane is missing.
    """
    specs = _envs(envs)
    row = _kernel.runs[run_id]
    backend = text(Space.planes[plane_id].props.backend)
    cell, cr = fresh("run_cell"), fresh("run_cell_run")
    each = nu.Let(
        cr,
        MintId("cr"),
        _add_cell_run(run_id, plane_id, nu.StrAttrRef(cell), nu.StrAttrRef(cr), by),
    )
    writes = (
        row.plane.set(plane_id)
        >> row.backend.set(backend)
        >> row.by.set(by)
        >> row.envs.set(specs)
        >> row.termination_requested.set(False)
        >> row.cells.init(nu.Literal({}))
        >> row.cells_running.init(nu.Literal(set()))
        >> row.latest.init(nu.Literal({}))
        >> row.workers.init(nu.Literal(set()))
        >> nu.ForEachDo(cells(plane_id), each, item=cell)
        >> _kernel.running.add(run_id)
    )
    return nu.IfDo(plane_exists(plane_id), writes)


def plane_run(
    plane_id: nu.StrArg,
    *,
    by: nu.StrArg = "",
    envs: Sequence[Sequence[str]] | nu.Nu = (),
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

    Yields:
        The run id, minted at evaluation. ``""`` when the plane is missing.
    """

    def write(rid_name: str) -> nu.Nu:
        rid = nu.StrAttrRef(rid_name)
        return nu.IfDo(
            plane_exists(plane_id),
            add_plane_run(rid, plane_id, by=by, envs=envs),
            nu.SetCmd(rid, nu.Str("")),
        )

    return atomic(binding(MintId("r"), write, tag="run"))


def add_cell_run(
    run_id: nu.StrArg, cell_id: nu.StrArg, cell_run_id: nu.StrArg, by: nu.StrArg = ""
) -> nu.Nu:
    """A cell run written into a live plane run, under ``cell_run_id``. No bracket.

    Nothing is written when the plane run is not live or its plane has no
    such cell.
    """
    plane = text(_kernel.runs[run_id].plane)
    live = nu.And(_kernel.running.contains(run_id), cell_exists(plane, cell_id))
    return nu.IfDo(live, _add_cell_run(run_id, plane, cell_id, cell_run_id, by))


def cell_run(run_id: nu.StrArg, cell_id: nu.StrArg, *, by: nu.StrArg = "") -> nu.Nu:
    """Run a cell inside a live plane run: a new cell run, beside any other of it. One commit.

    Yields:
        The cell run id, minted at evaluation. ``""`` when the plane run is
        not live or its plane has no such cell.
    """
    plane = text(_kernel.runs[run_id].plane)

    def write(cr_name: str) -> nu.Nu:
        cr = nu.StrAttrRef(cr_name)
        live = nu.And(_kernel.running.contains(run_id), cell_exists(plane, cell_id))
        return nu.IfDo(
            live, _add_cell_run(run_id, plane, cell_id, cr, by), nu.SetCmd(cr, nu.Str(""))
        )

    return atomic(binding(MintId("cr"), write, tag="cell_run"))


def interrupt(run_id: nu.StrArg, cell_run_id: nu.StrArg) -> nu.Nu:
    """Ask a live cell run to stop, unless it was asked already. No bracket."""
    ask = _kernel.runs[run_id].cells[cell_run_id].interrupt_requested
    live = _kernel.runs[run_id].cells_running.contains(cell_run_id)
    return nu.IfDo(nu.And(live, nu.Not(flag(ask, False))), ask.set(True))


def cell_interrupt(run_id: nu.StrArg, cell_run_id: nu.StrArg) -> nu.Nu:
    """Ask a cell run to stop. A no-op when it is not live. One commit.

    Cooperative: its body watches ``interrupt_requested`` and ends itself
    ``interrupted``. There is no cell kill: a backend may not be able to
    kill one cell alone, so kill is a plane op.
    """
    return atomic(interrupt(run_id, cell_run_id))


def _each_live_cell(run_id: nu.StrArg, body: Callable[[nu.StrAttrRef], nu.Nu]) -> nu.Nu:
    """``body(cell_run_id)`` for every live cell run of a plane run. No bracket."""
    item = fresh("live_cell")
    return nu.ForEachDo(
        nu.list(_kernel.runs[run_id].cells_running), body(nu.StrAttrRef(item)), item=item
    )


def plane_interrupt(run_id: nu.StrArg) -> nu.Nu:
    """Ask every live cell run of a plane run to stop. One commit.

    Once they have, ``cells_running`` is empty and the run ends.
    """
    return atomic(_each_live_cell(run_id, lambda cr: interrupt(run_id, cr)))


def kill(run_id: nu.StrArg) -> nu.Nu:
    """Ask the kernel to tear a live plane run down. No bracket."""
    ask = _kernel.runs[run_id].termination_requested
    return nu.IfDo(
        nu.And(_kernel.running.contains(run_id), nu.Not(flag(ask, False))), ask.set(True)
    )


def plane_kill(run_id: nu.StrArg) -> nu.Nu:
    """Tear a plane run down: its backend kills whatever runs it. One commit.

    Not cooperative: its live cell runs end ``killed`` without a say. A
    no-op when the run is not live.
    """
    return atomic(kill(run_id))


def _until_ended(run_id: nu.StrArg) -> nu.Nu:
    """Wait until a plane run is out of ``running``. Returns at once if it is."""
    wake = nu.Timeout(
        _WATCH, nu.React(_snap(_kernel.running.on_children_change())), on_timeout=nu.Delay(0.0)
    )
    return nu.WhileDo(_snap(_kernel.running.contains(run_id)), wake)


def plane_stop(run_id: nu.StrArg, grace: nu.FloatArg = STOP_GRACE) -> nu.Nu:
    """Interrupt a plane run, then kill it if it is still running after ``grace`` seconds.

    Two intents, written as they fall due. Returns once the run has ended,
    or once the kill is asked for: a caller waits ``grace`` at most.
    """
    return plane_interrupt(run_id) >> nu.Timeout(
        grace, _until_ended(run_id), on_timeout=plane_kill(run_id)
    )


# --- Unbracketed parts, for ops that take away what runs belong to ----------------------


def live_runs_of(match: Callable[[nu.Nu], nu.Nu], body: Callable[[nu.StrAttrRef], nu.Nu]) -> nu.Nu:
    """``body(run_id)`` for every live plane run whose plane ``match(plane)`` holds for. No bracket."""
    item = fresh("live_run")
    rid = nu.StrAttrRef(item)
    plane = text(_kernel.runs[rid].plane)
    return nu.ForEachDo(nu.list(_kernel.running), nu.IfDo(match(plane), body(rid)), item=item)


def interrupt_cell(plane_id: nu.StrArg, cell_id: nu.StrArg) -> nu.Nu:
    """Ask every live cell run of a cell, in any live run of its plane, to stop. No bracket."""

    def each(rid: nu.StrAttrRef) -> nu.Nu:
        def one(cr: nu.StrAttrRef) -> nu.Nu:
            same = nu.Eq(text(_kernel.runs[rid].cells[cr].cell), cell_id)
            return nu.IfDo(same, interrupt(rid, cr))

        return _each_live_cell(rid, one)

    return live_runs_of(lambda plane: nu.Eq(plane, plane_id), each)


# --- Reads ---------------------------------------------------------------------


def latest(run_id: nu.StrArg, cell_id: nu.StrArg) -> nu.Nu:
    """A cell's newest cell run in a plane run, live or ended, ``""`` when it has none. Bare read.

    A point read of the run's ``latest``: O(1) however many times the cell
    was reloaded or restarted in it.
    """
    row = _kernel.runs[run_id].latest
    return nu.If(row.contains(cell_id), nu.ToStr(row[cell_id]), nu.Str(""))


def _ids(ref: nu.Nu) -> nu.Nu:
    """A set of minted ids, oldest first."""
    return nu.List(nu.Collect(nu.Sorted(nu.list(ref))))


def _cell_run_row(run_id: nu.StrArg, cr: nu.StrAttrRef) -> nu.Nu:
    row = _kernel.runs[run_id].cells[cr]
    return nu.Dict.of(
        id=cr,
        cell=text(row.cell),
        version=or_else(row.version, 0),
        by=text(row.by),
        worker=text(row.worker),
        started_at=or_else(row.started_at, None),
        interrupt_requested=flag(row.interrupt_requested, False),
        terminated_at=or_else(row.terminated_at, None),
        exit=text(row.exit),
        error=text(row.error),
        out=or_else(row.out, []),
    )


def cell_runs(run_id: nu.StrArg, *, live: bool = False) -> nu.Nu:
    """A plane run's cell runs as dicts with their ``id``, oldest first. Bare read.

    Every one it ever had, or with ``live`` only those in ``cells_running``.
    """
    row = _kernel.runs[run_id]
    item = fresh("cell_runs")
    ids = _ids(row.cells_running) if live else nu.list(row.cells.keys())
    return nu.Collect(nu.Map(ids, _cell_run_row(run_id, nu.StrAttrRef(item)), key=item))


def _live_workers(rid: nu.StrArg) -> nu.Nu:
    """The plane run's live workers, oldest first. A walk of ``workers_running``, never its history."""
    item = fresh("run_workers")
    wid = nu.StrAttrRef(item)
    return nu.List(
        nu.Collect(
            nu.Filter(
                _ids(_kernel.workers_running), nu.Eq(text(_kernel.workers[wid].run), rid), key=item
            )
        )
    )


def _run_row(rid: nu.StrArg, *, whole: bool = False) -> nu.Nu:
    """A plane run as a dict. ``workers`` is every worker it had when ``whole``, else its live ones."""
    row = _kernel.runs[rid]
    return nu.Dict.of(
        id=rid,
        plane=text(row.plane),
        backend=text(row.backend),
        by=text(row.by),
        envs=or_else(row.envs, []),
        started_at=or_else(row.started_at, None),
        termination_requested=flag(row.termination_requested, False),
        terminated_at=or_else(row.terminated_at, None),
        exit=text(row.exit),
        error=text(row.error),
        cells_running=_ids(row.cells_running),
        latest=nu.If(row.latest.exists(), row.latest.extract(), nu.Literal({})),
        workers=_ids(row.workers) if whole else _live_workers(rid),
    )


def runs(plane: nu.StrArg | None = None) -> nu.Nu:
    """The live plane runs as dicts with their ``id``, oldest first. Bare read.

    Live is ``running``, so this reads in the time of what is live, its
    ``workers`` the live ones. With ``plane``, that plane's live runs only.
    A run's cell runs are :func:`cell_runs`; an ended run is read by id with
    :func:`run`.
    """
    item = fresh("runs")
    rid = nu.StrAttrRef(item)
    ids: nu.Nu = _ids(_kernel.running)
    if plane is not None:
        ids = nu.Filter(ids, nu.Eq(text(_kernel.runs[rid].plane), plane), key=item)
    return nu.Collect(nu.Map(ids, _run_row(rid), key=item))


def run(run_id: nu.StrArg) -> nu.Nu:
    """One plane run by id, live or ended, whole: every cell run under ``cells``, every worker. Bare read.

    The one read that walks a run's history, for inspecting it: O(what the
    run ever had). Nothing that runs on repeat reads it.
    """
    return nu.Dict(_run_row(run_id, whole=True)).merge(nu.Dict.of(cells=cell_runs(run_id)))


def workers() -> nu.Nu:
    """The live workers as dicts with their ``id``, oldest first. Bare read.

    ``handle`` is the backend's own, not for reading into.
    """
    item = fresh("workers")
    wid = nu.StrAttrRef(item)
    row = _kernel.workers[wid]
    return nu.Collect(
        nu.Map(
            _ids(_kernel.workers_running),
            nu.Dict.of(
                id=wid,
                backend=text(row.backend),
                run=text(row.run),
                plane=text(_kernel.runs[text(row.run)].plane),
                handle=text(row.handle),
                started_at=or_else(row.started_at, None),
            ),
            key=item,
        )
    )
