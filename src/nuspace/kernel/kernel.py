"""The kernel: one arm per live plane run, making the run records true through the backends.

The ops write what is wanted (``plane_run.add``, ``interrupt_at``,
``kill_at``); the kernel makes it so and writes what happened, through the
same ops. It folds over ``live.plane_runs``. An arm, for plane run ``r``::

    its plane and backend read, the backend's placement asked
    per plane run: a worker taken (worker.add, the backend launches it, worker.start)
    one commit: a cell run for each cell of the plane, then plane_run.start
    race
      cells     one arm per live cell run of r: a worker per cell run when
                the placement says so, cell_run.start, the body run by the
                backend until it ends (the body writes its own end)
      done      once r has no live cell run: its end, its workers let go
      due       once kill_at has passed: every live cell run, worker and r
                ended killed, the workers torn down
      requests  a newer interrupt_at fanned out to the live cell runs added
                before it; a removed or moved cell's live run interrupted;
                a removed plane's run stopped
    finally: whatever workers r still holds let go, and the one the arm took

The first cell runs land in one commit with ``started_at``, and the done
watch starts after it, so a plane run never reads empty before its cells
run, and reload (which skips plane runs not started) never adds a first
run beside the kernel's.

A plane run's exit: ``killed`` when ``kill_at`` passed; else ``failed``
when its failed cells set is not empty (a cell's last cell run in it
failed), whether or not an interrupt was asked; else ``interrupted`` when
one was (``interrupt_at``), ``ok`` otherwise. Failed wins over interrupted
so a policy restarting failed runs sees the failure.

Every fold here is level and opts in to the standard re-checks
(``nu.RECHECK_AFTER``, ``nu.RECHECK_EVERY``): a missed notification would
leave a run unplaced, unended, unkilled or uninterrupted.

Both folds run each arm once per appearance of its id, and an arm that
raises would end its whole fold. So every arm catches its own: a raise is
reported on stdout and ends that run or cell run ``failed`` with the error
text (unless it ended already), its cleanup still runs, and nothing else
dies. Should even that end fail (the store gone), the arm reports and
finishes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nustd.time
from nuspace import ops
from nuspace.ops.brackets import atomic
from nuspace.shapes import EXIT_FAILED, EXIT_INTERRUPTED, EXIT_KILLED, EXIT_OK, Space
from nuspace.utils import keys_of
from nuspace.utils.policies import report

from .backends import PER_CELL_RUN, PER_PLANE_RUN, BackendRef, Kill, Launch, Placement, Run, Stop
from .backends import provided as provided_backends
from .envs import KernelConfig
from .interactions import Body, ErrorText
from .records import (
    cell_runs_of,
    end_cell_run,
    end_plane_run,
    end_worker,
    workers_of,
)


if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from .backends import Backend
    from .envs import EnvFactory


__all__ = ["bound", "kernel"]


_exec = Space.exec
_live = Space.exec.indexes.live

#: The standard re-check schedule every fold here opts in to.
_RECHECK = {"after": nu.RECHECK_AFTER, "every": nu.RECHECK_EVERY}

#: A cell run whose body came back without writing its end.
UNENDED = "Cell run's body returned without writing its end"

#: A cell run started by an arm that is gone, so nothing runs it.
ORPHAN = "Cell run lost its kernel arm"


# --- containment -----------------------------------------------------------------


def _contained(arm: nu.Nu, fail: Callable[[nu.StrArg], nu.Nu], name: str, id: nu.StrArg) -> nu.Nu:
    """``arm``, a raise out of it reported, then ``fail`` given the error text to write the end.

    Reported first, since the record may have ended already and the end
    would drop the text. A raise out of ``fail`` is reported too, so the
    arm always finishes and its fold keeps going.
    """
    return nu.TryCatch(
        arm,
        catch=lambda err: (
            report(name, id, ErrorText(err))
            >> nu.TryCatch(
                nu.let(ErrorText(err), fail), catch=lambda again: report(name, id, ErrorText(again))
            )
        ),
    )


# --- workers ------------------------------------------------------------------------


def _launch(worker: nu.Str, backend: nu.Str) -> nu.Nu:
    """The backend brings ``worker`` up, then ``worker.start`` with its handle.

    A launch that raises ends the worker failed, then raises on, so what
    wanted the worker fails with it.
    """

    def failed(err: nu.Nu) -> nu.Nu:
        def ended(why: nu.ObjectRef) -> nu.Nu:
            msg = nu.Str("Backend failed to launch a worker: ") + nu.Str(why)
            return atomic(end_worker(worker, EXIT_FAILED, why)) >> nu.Raise(msg)

        return nu.let(ErrorText(err), ended)

    up = nu.let(
        Launch(BackendRef(backend), worker),
        lambda handle: atomic(ops.worker.start(worker, handle=handle)),
    )
    return nu.TryCatch(up, catch=failed)


def _take(plane_run: nu.Str, backend: nu.Str, into: nu.Ref) -> nu.Nu:
    """A worker for the plane run: its record (the kernel mints the id into ``into``), then launched."""
    return atomic(ops.worker.add(plane_run, backend, into=into)) >> _launch(nu.Str(into), backend)


def _the_worker(plane_run: nu.Str) -> nu.Nu:
    """A plane run's one live worker, ``""`` when it holds none. For a per plane run placement."""
    return _live.plane_run_to_workers[plane_run].ids.first().fallback("")


# --- the end -----------------------------------------------------------------------


def _ends(plane_run: nu.Str, exit: nu.StrArg, error: nu.StrArg, worker_exit: str) -> nu.Nu:
    """Every live cell run and worker of the plane run ended, then the run. Bare, one commit's worth."""
    return (
        nu.ForEachDo(cell_runs_of(plane_run), lambda cr: end_cell_run(nu.Str(cr), exit, error))
        >> nu.ForEachDo(workers_of(plane_run), lambda w: end_worker(nu.Str(w), worker_exit))
        >> end_plane_run(plane_run, exit, error)
    )


def _teardown(
    plane_run: nu.Str,
    backend: nu.Str,
    exit: nu.StrArg,
    error: nu.StrArg = "",
    *,
    killed: bool = False,
    when: nu.Nu | None = None,
) -> nu.Nu:
    """End the plane run in one commit, then let its workers go.

    The records first, so a body failing because its worker went finds its
    end written already. Then the workers it held when asked, torn down now
    with ``killed``, let go politely otherwise, shielded either way. The
    arm is cancelled as the run leaves the live set, which the commit does,
    so a cancel can land before the let go: the arm's ``finally``
    (:func:`_release`) stops the worker it took, not trusting the live set.

    Args:
        plane_run: The run.
        backend: Its backend's name.
        exit: The exit, its live cell runs' too.
        error: Why, for a failure.
        killed: Workers end ``killed`` and are torn down now; else ``ok``,
            let go politely.
        when: A condition checked inside the commit; false, nothing is
            written and nothing let go.
    """
    row = _exec.plane_runs[plane_run]
    worker_exit = EXIT_KILLED if killed else EXIT_OK
    ends = _ends(plane_run, exit, error, worker_exit)
    if when is not None:
        ends = nu.IfDo(when, ends)
    let_go = Kill if killed else Stop

    def go(held: nu.ObjectRef) -> nu.Nu:
        commit = atomic(ends)
        return commit >> nu.IfDo(atomic(row.ended_at.exists()), let_go(BackendRef(backend), held))

    return nu.let(atomic(workers_of(plane_run)), go)


def _release(plane_run: nu.Str, backend: nu.Str, taken: nu.Ref) -> nu.Nu:
    """Let go of whatever workers the plane run still holds, and ``taken``. Its arm's ``finally``.

    After a clean end the run holds none. On a raise or a cancel (the space
    closing) the records still list them: their processes go now, their
    records end with the run (on a raise) or at the host's close (on a
    close, :mod:`.close`).
    ``taken`` is the worker the arm took for a per plane run placement
    (``""`` for none): a cancel between the end's commit and its let go
    finds the live set empty already, so it is stopped by id. Stop is
    idempotent, so stopping it twice is nothing.
    """
    ref = BackendRef(backend)
    own = nu.Str(taken)
    held = nu.let(atomic(workers_of(plane_run)), lambda ids: Stop(ref, ids))
    return held >> nu.IfDo(own != "", Stop(ref, nu.List.of(own)))


# --- the race -----------------------------------------------------------------------


def _cell_arm(plane_run: nu.Str, cell_run: nu.Str, backend: nu.Str, placement: nu.Str) -> nu.Nu:
    """One live cell run: a worker, ``cell_run.start``, its body run by the backend to its end.

    The body writes its own end. A worker that died under it is the cell
    run and the worker ending ``failed`` with why, in one commit. A cell
    run back from its body without an end is ended ``failed`` here, or it
    would hold its plane run open for good. A cell run already started was
    started by an arm that is gone, so nothing runs it: it ends ``failed``.

    Cancelled, which is the cell run leaving the live set, the body is
    cancelled where it runs. Any raise ends the cell run ``failed`` with
    the error text. With a worker of its own (``PER_CELL_RUN``), the worker
    is let go once the arm is over, however it ends, and ended ``ok`` when
    its cell run has ended. Cancelled with the cell run still live (the
    space closing), its record is left to the close, or to the next reap.
    """
    row = _exec.cell_runs[cell_run]
    run_row = _exec.plane_runs[plane_run]
    ref = BackendRef(backend)
    own = placement == PER_CELL_RUN

    def failed(why: nu.StrArg) -> nu.Nu:
        return atomic(end_cell_run(cell_run, EXIT_FAILED, why))

    def with_slot(slot: nu.ObjectRef) -> nu.Nu:
        worker = nu.Str(slot)
        shared = atomic(slot.set(_the_worker(plane_run))) >> nu.IfDo(
            worker == "",
            nu.Raise(nu.Str("Plane run ") + plane_run + " holds no worker: it died, or was let go"),
        )
        take = nu.IfDo(own, _take(plane_run, backend, slot), shared)
        body = Body(
            plane_run,
            cell_run,
            atomic(run_row.plane),
            atomic(row.cell),
            atomic(run_row.envs.fallback(nu.Literal([]))),
        )

        def lost(why: nu.ObjectRef) -> nu.Nu:
            ended = end_cell_run(cell_run, EXIT_FAILED, why) >> end_worker(worker, EXIT_FAILED, why)
            return nu.IfDo(nu.Str(why) != "", atomic(ended))

        unended = nu.IfDo(atomic(row.ended_at.exists().not_()), failed(UNENDED))
        go = (
            take
            >> atomic(ops.cell_run.start(cell_run, worker=worker))
            >> nu.let(Run(ref, worker, cell_run, body), lost)
            >> unended
        )
        once = nu.IfDo(atomic(row.started_at.exists()), failed(ORPHAN), go)
        over = nu.IfDo(row.ended_at.exists(), end_worker(worker, EXIT_OK))
        release = nu.IfDo(own.and_(worker != ""), Stop(ref, nu.List.of(worker)) >> atomic(over))
        # A raise ends the cell run before the release reads whether it ended.
        return nu.TryCatch(_contained(once, failed, "kernel cell run", cell_run), finally_=release)

    return _contained(nu.let("", with_slot), failed, "kernel cell run", cell_run)


def _cells(plane_run: nu.Str, backend: nu.Str, placement: nu.Str) -> nu.Nu:
    """:func:`_cell_arm` for every live cell run of the plane run, births and deaths included."""
    ids = _live.plane_run_to_cell_runs[plane_run].ids
    return nu.ReconcileLatestEach(
        atomic(keys_of(ids)),
        atomic(ids.on_children_change()),
        lambda cr: _cell_arm(plane_run, nu.Str(cr), backend, placement),
        **_RECHECK,
    )


def _done(plane_run: nu.Str, backend: nu.Str) -> nu.Nu:
    """End the plane run once it has no live cell run. Returns once it has ended.

    The emptiness is checked again inside the end's commit, so a cell run
    added meanwhile (reload) keeps the run going. The exit is read there
    too: ``failed`` when a cell's last run failed, even after an interrupt.
    """
    row = _exec.plane_runs[plane_run]
    ids = _live.plane_run_to_cell_runs[plane_run].ids
    empty = nu.Bool(nu.If(ids.exists(), nu.Not(ids), False))
    failed_cells = _live.plane_run_to_failed_cells[plane_run].ids
    failed = nu.Bool(nu.If(failed_cells.exists(), nu.Not(failed_cells), True)).not_()
    asked = nu.If(row.interrupt_at.exists(), EXIT_INTERRUPTED, EXIT_OK)
    exit = nu.If(failed, EXIT_FAILED, asked)
    end = _teardown(plane_run, backend, exit, when=empty)
    return nu.ReconcileWhile(
        atomic(ids.on_children_change()),
        atomic(row.ended_at.exists().not_()),
        nu.IfDo(atomic(empty), end),
        **_RECHECK,
    )


def _due(plane_run: nu.Str, backend: nu.Str) -> nu.Nu:
    """Once ``kill_at`` has passed: the plane run torn down, everything of it ended ``killed``.

    A ``kill_at`` moved earlier restarts the wait.
    """
    kill_at = _exec.plane_runs[plane_run].kill_at

    def wait(at: nu.Nu) -> nu.Nu:
        left = nu.Float(at) - nustd.time.time()
        return nu.Delay(left) >> _teardown(plane_run, backend, EXIT_KILLED, killed=True)

    return nu.ReconcileLatest(atomic(kill_at), atomic(kill_at.on_change()), wait, **_RECHECK)


def _wanted_interrupt(cell_run: nu.Str, plane: nu.Str, asked: nu.Nu) -> nu.Bool:
    """Whether a live cell run is to be interrupted. A read.

    By the plane run: it was added before the plane run's ``interrupt_at``
    and not asked since. By its cell: removed, or moved off the plane, and
    not asked yet.
    """
    row = _exec.cell_runs[cell_run]
    cell = Space.cells[row.cell]
    mine = row.interrupt_at
    newer = nu.If(mine.exists(), mine < asked, True)
    by_run = nu.If(asked.exists(), nu.If(row.created_at < asked, newer, False), False)
    gone = cell.removed_at.exists().or_(cell.plane != plane)
    by_cell = nu.If(mine.exists(), False, gone)
    return nu.Bool(by_run).or_(nu.Bool(by_cell))


def _asked(plane_run: nu.Str, plane: nu.Str) -> nu.Nu:
    """One pass over what was asked of the run: removals and interrupts made true. Bare.

    A removed plane gets its run stopped once (interrupt now, kill after
    the stop grace). Every live cell run :func:`_wanted_interrupt` names
    gets ``cell_run.interrupt``. Settles: a second pass with nothing new
    writes nothing.
    """
    row = _exec.plane_runs[plane_run]
    removed = Space.planes[plane].removed_at
    asked = row.interrupt_at
    unasked = nu.If(asked.exists(), asked < removed, True)
    stop = nu.IfDo(
        removed.exists().and_(nu.Bool(unasked)),
        ops.plane_run.stop(plane_run),
    )
    fan_out = nu.ForEachDo(
        cell_runs_of(plane_run),
        lambda cr: nu.IfDo(
            _wanted_interrupt(nu.Str(cr), plane, asked), ops.cell_run.interrupt(nu.Str(cr))
        ),
    )
    return stop >> fan_out


def _requests(plane_run: nu.Str, plane: nu.Str) -> nu.Nu:
    """:func:`_asked` on every change to the plane run's row or its plane's row, one commit a pass.

    The plane row is one prefix watch: removal, the cells list, a moved
    cell's version bump all land in it.
    """
    change = nu.OnAny(
        atomic(Space.planes[plane].on_change()),
        atomic(_exec.plane_runs[plane_run].on_change()),
    )
    return nu.Reconcile(change, atomic(_asked(plane_run, plane)), **_RECHECK)


# --- the arm ------------------------------------------------------------------------


def _first_runs(plane_run: nu.Str, plane: nu.Str) -> nu.Nu:
    """A cell run for each cell of the plane, then ``plane_run.start``. Bare, one commit's worth.

    Inherently O(cells). A cell with a run in this plane run already (a
    retried commit) or removed is skipped.
    """
    row = _exec.plane_runs[plane_run]
    node = _exec.indexes.history.plane_to_plane_runs[plane].runs[plane_run]

    def first(c: nu.Nu) -> nu.Nu:
        cell = nu.Str(c)
        fresh = node.cell_to_cell_runs.contains(cell).not_()
        kept = Space.cells[cell].removed_at.exists().not_()
        return nu.IfDo(fresh.and_(kept), ops.cell_run.add(plane_run, cell, by=row.by))

    cells = nu.list(Space.planes[plane].cells.keys())
    return nu.ForEachDo(cells, first) >> ops.plane_run.start(plane_run)


def _life(plane_run: nu.Str, plane: nu.Str, backend: nu.Str, taken: nu.Ref) -> nu.Nu:
    """A plane run's life once its plane and backend are known. See the module doc.

    A per plane run placement takes its worker into ``taken``.
    """

    def placed(placement: nu.ObjectRef) -> nu.Nu:
        how = nu.Str(placement)
        return (
            nu.IfDo(how == PER_PLANE_RUN, _take(plane_run, backend, taken))
            >> atomic(_first_runs(plane_run, plane))
            >> nu.Race(
                _cells(plane_run, backend, how),
                _done(plane_run, backend),
                _due(plane_run, backend),
                _requests(plane_run, plane),
            )
        )

    return nu.let(Placement(BackendRef(backend)), placed)


def _arm(plane_run: nu.Str) -> nu.Nu:
    """One plane run's whole life in the host. Runs once per appearance in ``live.plane_runs``.

    It finishes once the run has ended, or the fold cancels it as the run
    leaves the live set. A raise anywhere in it is reported and ends the
    run ``failed`` with the error text, its live cell runs with it; its
    workers are let go first.
    """
    row = _exec.plane_runs[plane_run]

    def named(plane: nu.ObjectRef, backend: nu.ObjectRef) -> nu.Nu:
        p, b = nu.Str(plane), nu.Str(backend)

        def failed(why: nu.StrArg) -> nu.Nu:
            return _teardown(plane_run, b, EXIT_FAILED, why)

        def life(taken: nu.ObjectRef) -> nu.Nu:
            return nu.TryCatch(
                _life(plane_run, p, b, taken), finally_=_release(plane_run, b, taken)
            )

        return _contained(nu.let("", life), failed, "kernel plane run", plane_run)

    known = nu.let(
        atomic(row.plane.fallback("")),
        lambda plane: nu.let(atomic(row.backend.fallback("")), lambda b: named(plane, b)),
    )
    return nu.TryCatch(
        known, catch=lambda err: report("kernel plane run", plane_run, ErrorText(err))
    )


def kernel() -> nu.Nu:
    """The kernel driver: :func:`_arm` for every plane run in ``live.plane_runs``. Never returns.

    Needs :func:`bound` around it, inside the stores and the worker pool,
    and reap run before it (``nuspace.kernel.reap``): it trusts the live
    indexes. Nobody calls it but the host.
    """
    plane_runs = _live.plane_runs
    return nu.ReconcileLatestEach(
        atomic(keys_of(plane_runs)),
        atomic(plane_runs.on_children_change()),
        lambda r: _arm(nu.Str(r)),
        **_RECHECK,
    )


def bound(
    *,
    backends: Mapping[str, type[Backend]] | None = None,
    envs: Mapping[str, EnvFactory] | None = None,
    space_envs: Sequence[Sequence[str] | str] = (),
) -> nu.With:
    """What the kernel needs bound around it: the backends and its config.

    Goes inside the stores and the worker pool, which the process backends
    take from.

    Args:
        backends: Backend classes by name, on top of the built in ``async``
            and ``mp``.
        envs: Env factories by name (:mod:`~nuspace.kernel.envs`).
        space_envs: Env specs every plane run executes inside, outermost.
    """
    return nu.With(
        provided_backends(backends),
        nu.Provide(KernelConfig, {"envs": envs, "space_envs": space_envs}),
    )
