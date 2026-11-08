"""The body of one cell run: built in the host, handed to a backend, run on a worker.

Everything a cell run is on its worker, as one Nu term with its ids baked
in as plain strs::

    Frame(Here: plane, cell, plane_run, cell_run)
      With(Captured)                       out, told apart per cell run
        TryCatch(                          raised: exit failed, error, traceback
          envs' wraps, space-wide outermost
            Race(program, interrupt watch, out flusher)
            exit ok, or interrupted when an interrupt was asked
        the end: the last out, cell_run.end, one commit

The kernel wrote ``cell_run.start`` before handing the body over; the body
writes its own end, so its output never travels back to the host. An end
already written (the run was killed, its worker torn down) is kept.

The program is loaded on the worker from the store, so a cell run always
runs the prog as it is now, through each env's rewrite. Nothing brackets
it: a program brackets its own store access (``nuspace.atomic``,
``nuspace.bracketed``). The body's own reads and writes are short brackets
of their own, never held while the program runs.

Interrupt is cooperative and backend agnostic: the body watches its own
``CellRun.interrupt_at`` and leaves once it is set, so every backend gets
it for free. Kill is the kernel's, through the backend.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nu.prog
from nuspace import ops
from nuspace.ops.brackets import atomic
from nuspace.places import Here
from nuspace.shapes import EXIT_FAILED, EXIT_INTERRUPTED, EXIT_OK, Space

from .interactions import Captured, ErrorText, HasOut, TakeOut


if TYPE_CHECKING:
    from collections.abc import Sequence

    from nu.tree import Transform

    from .envs import Env


__all__ = ["FLUSH_SECONDS", "Rewrites", "build_body"]


#: How often a cell run's waiting output is written to its record, in seconds.
FLUSH_SECONDS = 1.0


class _Ending(nu.Shape):
    """What a cell run's last write works out before its commit: the output left, why it failed."""

    out = nu.ObjectRef.slot()
    why = nu.StrRef.slot()


class Rewrites:
    """Transforms applied in order, as one ``Nu -> Nu``. Picklable if its steps are."""

    __slots__ = ("steps",)

    def __init__(self, *steps: Transform) -> None:
        self.steps = steps

    def __call__(self, term: nu.Nu) -> nu.Nu:
        """``term`` through every step, first to last."""
        for step in self.steps:
            term = step(term)
        return term


def _flush(cell_run: str) -> nu.Nu:
    """Append waiting output to the record, if there is any. One commit."""
    out = Space.exec.cell_runs[cell_run].out
    return nu.IfDo(HasOut(), nu.let(TakeOut(), lambda taken: atomic(out.extend(taken))))


def _finish(
    cell_run: str,
    exit: nu.StrArg,
    *,
    error: nu.Nu | None = None,
    extra: nu.Nu | str = "",
) -> nu.Nu:
    """The last write: the output left, then ``cell_run.end``. One commit, skipped once ended.

    The output and the error text are worked out before the commit, so a
    retry on conflict takes nothing twice.
    """
    row = Space.exec.cell_runs[cell_run]
    why = "" if error is None else _Ending.why
    end = row.out.extend(_Ending.out) >> ops.cell_run.end(cell_run, exit, why)
    commit = atomic(nu.IfDo(row.ended_at.exists().not_(), end))
    fields: dict[str, object] = {"out": TakeOut(extra, final=True)}
    if error is not None:
        fields["why"] = error
    return nu.Frame(_Ending, commit, **fields)


def build_body(
    plane_run: str,
    cell_run: str,
    plane: str,
    cell: str,
    envs: Sequence[Env] = (),
) -> nu.Nu:
    """One cell run's whole life on its worker, as a term to run there.

    Args:
        plane_run: The plane run's id.
        cell_run: The cell run's id.
        plane: The plane id.
        cell: The cell id.
        envs: Resolved envs, outermost first. Their wraps are applied here,
            in the host; their rewrites ride along onto the worker.

    Returns:
        A picklable term. Holds :class:`~nuspace.places.Here` in a frame
        for the program and its envs.
    """
    steps = [env.rewrite for env in envs if env.rewrite is not None]
    rewrite = Rewrites(*steps) if steps else None
    source = Space.cells[cell].prog
    # The prog is read in a snapshot of its own, closed before the program runs.
    load = atomic(source.load(scope={"plane": plane, "cell": cell}, rewrite=rewrite))
    # On the loop: a program that subscribes is async only.
    program = nu.ParallelAsync(nu.prog.Eval(load))
    row = Space.exec.cell_runs[cell_run]
    asked = row.interrupt_at.exists()
    # Level: a missed notification would leave the cell running, so re-check.
    interrupted = nu.WaitUntil(
        atomic(row.interrupt_at.on_change()),
        atomic(asked),
        after=nu.RECHECK_AFTER,
        every=nu.RECHECK_EVERY,
    )
    flusher = nu.ForeverDo(nu.Delay(FLUSH_SECONDS) >> _flush(cell_run))
    # The record says why the race ended: an asked interrupt, or the program
    # finishing. The flusher never wins.
    run = nu.Race(program, interrupted, flusher) >> _finish(
        cell_run, nu.If(atomic(asked), EXIT_INTERRUPTED, EXIT_OK)
    )
    for env in reversed(envs):
        if env.wrap is not None:
            run = env.wrap(run)
    # Outside the wraps, so an env failing to open is this cell run failing.
    caught = nu.TryCatch(
        run,
        catch=lambda err: _finish(
            cell_run, EXIT_FAILED, error=ErrorText(err), extra=ErrorText(err, full=True)
        ),
    )
    body = nu.With(Captured(), body=caught)
    return nu.Frame(Here, body, plane=plane, cell=cell, plane_run=plane_run, cell_run=cell_run)
