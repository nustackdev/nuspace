"""``nuspace.plane_run``: the ops over ``Space.exec.plane_runs``, one per lifecycle slot.

``add`` writes ``created_at``, ``start`` ``started_at``, ``interrupt``
``interrupt_at``, ``kill`` ``kill_at``, ``end`` ``ended_at``; ``stop`` writes
two. ``add``, ``interrupt``, ``kill`` and ``stop`` ask; ``start`` and ``end``
are the kernel saying what happened. Calling those by hand records a fact
the kernel did not see.

Declarative: nothing here starts or stops a process. The kernel watches
the records and the live indexes and makes them true.

Every op is a bare term the caller brackets (see :mod:`nuspace.ops`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nustd.time
from nuspace.errors import Missing, Refused
from nuspace.shapes.exec import EXIT_FAILED, EXIT_OK
from nuspace.shapes.space import Space
from nuspace.utils import MintId, Require
from nuspace.utils.checks import exit_known, live, not_ended, refuse, row_known, text


if TYPE_CHECKING:
    from collections.abc import Sequence


__all__ = [
    "STOP_GRACE",
    "add",
    "any_live",
    "end",
    "interrupt",
    "kill",
    "on_live_change",
    "start",
    "stop",
    "wait",
]


#: How long ``stop`` gives a plane run after its interrupt before its kill falls due, in seconds.
STOP_GRACE = 10.0


def _envs(envs: Sequence[Sequence[str]] | nu.Nu) -> object:
    """Env specs, ``[name, *args]`` each, as a value ``PlaneRun.envs`` stores whole."""
    if isinstance(envs, nu.Nu):
        return envs
    return nu.Literal([list(spec) for spec in envs])


def add(
    plane: nu.StrArg,
    *,
    by: nu.StrArg = "",
    envs: Sequence[Sequence[str]] | nu.Nu = (),
    into: nu.Ref | None = None,
) -> nu.Nu:
    """Ask for a run of a plane: a new plane run record. Starts nothing, the kernel does.

    One commit: the row (plane, the plane's backend as it is now, by, envs,
    created_at), its node in ``history``, and the live indexes: into
    ``live.plane_runs`` (what the kernel folds over) and
    ``live.plane_to_plane_runs[plane]``, with its own live sets made empty.
    The kernel adds its cell runs. Cost: O(1), about 12 keys.

    Args:
        plane: The plane to run.
        by: Who asked, eg ``nav``.
        envs: Env specs its cells run inside, outermost first, each
            ``[name, *args]`` naming a factory registered at open.
        into: A ref set to the new run's id in the same commit.

    Raises:
        Missing: No plane with that id.
        Removed: It is removed.
        Refused: It has no backend (root), so it does not run.
    """
    planes = Space.planes
    indexes = Space.exec.indexes

    def write(rid: nu.ObjectRef) -> nu.Nu:
        r = nu.Str(rid)
        row = Space.exec.plane_runs[r]
        node = indexes.history.plane_to_plane_runs[plane].runs[r]
        held = indexes.live
        writes = (
            row.plane.set(plane)
            >> row.backend.set(planes[plane].backend)
            >> row.by.set(by)
            >> row.envs.set(_envs(envs))
            >> row.created_at.set(nustd.time.time())
            >> node.cell_to_cell_runs.set(nu.Dict.create())
            >> node.workers.set(nu.Dict.create())
            >> held.plane_runs.set_item(r, True)
            >> held.plane_to_plane_runs[plane].ids.set_item(r, True)
            >> held.plane_run_to_cell_runs[r].ids.set(nu.Dict.create())
            >> held.plane_run_to_failed_cells[r].ids.set(nu.Dict.create())
            >> held.plane_run_to_workers[r].ids.set(nu.Dict.create())
        )
        return writes if into is None else writes >> into.set(r)

    backend = planes[plane].backend.fallback("")
    return (
        live(planes, plane, "plane")
        >> refuse(backend == "", Refused, "plane ", plane, " has no backend, so it does not run")
        >> nu.let(MintId("r"), write)
    )


def start(plane_run: nu.StrArg) -> nu.Nu:
    """Observed, by the kernel: the run is really up. Writes ``started_at`` once. Cost: O(1), 1 key.

    Raises:
        Missing: No plane run with that id.
        Ended: It already ended.
    """
    runs = Space.exec.plane_runs
    return not_ended(runs, plane_run, "plane run") >> runs[plane_run].started_at.init(
        nustd.time.time()
    )


def _unless_ended(plane_run: nu.StrArg, write: nu.Nu) -> nu.Nu:
    """``write`` on a known plane run, a no-op on one that ended: a race that harms nothing."""
    runs = Space.exec.plane_runs
    return row_known(runs, plane_run, "plane run") >> nu.IfDo(
        runs[plane_run].ended_at.exists().not_(), write
    )


def _kill_by(plane_run: nu.StrArg, when: nu.Nu) -> nu.Nu:
    """Set ``kill_at`` to ``when``, or keep an earlier one: the earliest wins."""
    kill_at = Space.exec.plane_runs[plane_run].kill_at
    earlier = kill_at.exists().and_(kill_at <= when)
    return kill_at.set(nu.If(earlier, kill_at, when))


def interrupt(plane_run: nu.StrArg) -> nu.Nu:
    """Ask the kernel to interrupt the run's live cell runs: ``interrupt_at = now``.

    The kernel interrupts those started before it; the plane run goes on. A
    repeat is a newer time. A no-op on a run that ended. Cost: O(1), 1 key.

    Raises:
        Missing: No plane run with that id.
    """
    at = Space.exec.plane_runs[plane_run].interrupt_at
    return _unless_ended(plane_run, at.set(nustd.time.time()))


def kill(plane_run: nu.StrArg) -> nu.Nu:
    """Ask the kernel to kill the run now: ``kill_at = now``, or an earlier one kept.

    Not cooperative: once ``kill_at`` has passed the kernel tears the run
    down. A no-op on a run that ended. Cost: O(1), 1 key.

    Raises:
        Missing: No plane run with that id.
    """
    return _unless_ended(plane_run, nu.let(nustd.time.time(), lambda now: _kill_by(plane_run, now)))


def stop(plane_run: nu.StrArg, *, grace: nu.FloatArg = STOP_GRACE) -> nu.Nu:
    """Interrupt now, kill later if still running: ``interrupt_at = now``, ``kill_at = now + grace``.

    An earlier ``kill_at`` stays. No op waits: :func:`wait` does, if the
    caller wants to. A no-op on a run that ended. Cost: O(1), 2 keys.

    Raises:
        Missing: No plane run with that id.
    """
    at = Space.exec.plane_runs[plane_run].interrupt_at

    def asked(now: nu.ObjectRef) -> nu.Nu:
        return at.set(now) >> _kill_by(plane_run, nu.Float(now) + grace)

    return _unless_ended(plane_run, nu.let(nustd.time.time(), asked))


def wait(plane_run: nu.StrArg) -> nu.Nu:
    """Return once the store says the run ended. At once when it already has.

    A watch on the run's own row, level: it re-reads ``ended_at`` on every
    change and on the standard re-check schedule, so a missed notification
    is late, never lost. Bracket it with ``nuspace.bracketed``, never
    ``nuspace.atomic``: a snapshot held over the wait would never see the
    end. Cost: O(1), one subscription and one read per wake.

    Raises:
        Missing: No plane run with that id.
    """
    runs = Space.exec.plane_runs
    row = runs[plane_run]
    return row_known(runs, plane_run, "plane run") >> nu.WaitUntil(
        row.on_change(),
        row.ended_at.exists(),
        after=nu.RECHECK_AFTER,
        every=nu.RECHECK_EVERY,
    )


def end(plane_run: nu.StrArg, exit: nu.StrArg, error: nu.StrArg = "") -> nu.Nu:
    """Observed, by the kernel: the run is over. Writes ``ended_at``, ``exit``, ``error``.

    Out of ``live.plane_runs`` and its plane's live runs; its failed cells
    set is dropped, and its live cell run and worker sets when empty. An
    ``ok`` exit is written ``failed`` when a cell's last cell run in it
    failed (``live.plane_run_to_failed_cells[r]`` not empty). Cost: O(1),
    about 9 keys.

    Args:
        plane_run: The run.
        exit: How it ended, one of :data:`~nuspace.shapes.exec.EXITS`.
        error: Why it failed, ``""`` for none.

    Raises:
        Missing: No plane run with that id.
        Ended: It already ended: ending twice is a driver bug.
        Refused: An exit none of ``EXITS`` (a literal at build).
    """
    runs = Space.exec.plane_runs
    row = runs[plane_run]
    held = Space.exec.indexes.live
    failed = nu.Bool(nu.Not(held.plane_run_to_failed_cells[plane_run].ids)).not_()
    told = nu.If((nu.Str(exit) == EXIT_OK).and_(failed), EXIT_FAILED, exit)
    cells = held.plane_run_to_cell_runs[plane_run]
    workers = held.plane_run_to_workers[plane_run]
    return (
        exit_known(exit)
        >> not_ended(runs, plane_run, "plane run")
        >> row.exit.set(told)
        >> row.error.set(error)
        >> row.ended_at.set(nustd.time.time())
        >> held.plane_runs.del_item(plane_run)
        >> held.plane_to_plane_runs[row.plane].ids.del_item(plane_run)
        >> held.plane_run_to_failed_cells[plane_run].erase()
        >> nu.IfDo(nu.Not(cells.ids), cells.erase())
        >> nu.IfDo(nu.Not(workers.ids), workers.erase())
    )


def any_live(plane: nu.StrArg) -> nu.Bool:
    """Whether the plane has a live plane run. A read. Cost: O(1), about 3 reads.

    Raises:
        Missing: No plane with that id.
    """
    ids = Space.exec.indexes.live.plane_to_plane_runs[plane].ids
    has = nu.If(ids.exists(), nu.Bool(nu.Not(ids)).not_(), False)
    known = Space.planes.contains(plane)
    return nu.Bool(Require(known, has, text("no plane ", plane), exc_cls=Missing))


def on_live_change(*, plane: nu.StrArg | None = None) -> nu.Nu:
    """A watch: a plane run was added to or ended out of the live set. One kv subscription.

    Every plane's runs, or one plane's with ``plane``. Never raises.
    """
    held = Space.exec.indexes.live
    if plane is None:
        return held.plane_runs.on_change()
    return held.plane_to_plane_runs[plane].ids.on_change()
