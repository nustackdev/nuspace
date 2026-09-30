"""The body of one cell run: built in the host, handed to a backend, run on a worker.

Everything a cell run is, as one Nu term with its ids baked in as plain strs::

    Let(plane, cell, run, cell run ids)
      With(Captured)                       out, attributed to this cell run
        TryCatch(                          raised: exit failed, error, traceback
          envs' wraps, space-wide outermost
            mark started
            Race(program, interrupt watch, out flusher)
            exit ok, or interrupted when the watch won
        the end: out, exit, terminated_at, out of cells_running

The program is loaded on the worker from the store, so a cell run always
runs the prog as it is now. Its term is rewritten on the way in: reroot
first, then each env's rewrite, then the kv brackets, one pass per store
(D23: a state ref only belongs to States once rerooted). The kernel's own
record writes are short transactions of their own, never held open while
the program runs.

Interrupt is cooperative and backend agnostic: the body watches its own
``interrupt_requested`` and leaves when it reads true, so every backend gets
it for free. Kill is a plane op, the backend's.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nu.prog
import nustd.kv
from nuspace.ops import CELL_ATTR, CELL_RUN_ATTR, PLANE_ATTR, RUN_ATTR
from nuspace.ops.utils import atomic, flag
from nuspace.shapes import EXIT_FAILED, EXIT_INTERRUPTED, EXIT_OK, Reroot, Space, States

from .out import Captured, ErrorText, HasOut, TakeOut
from .utils import Now, until


if TYPE_CHECKING:
    from collections.abc import Sequence

    from nu.tree import Transform

    from .envs import Env


__all__ = ["FLUSH_SECONDS", "Bracketed", "Rewrites", "build_body", "end_cell_run"]


#: How often a cell run's waiting output is written to its record.
FLUSH_SECONDS = 1.0

_kernel = Space.kernel

# One body per context: a run request carries attrs, so the worker runs each
# body on a context copy of its own and these names cannot collide.
_OUTCOME = "nuspace.kernel.outcome"
_ERROR = "nuspace.kernel.error"
_OUT = "nuspace.kernel.out"
_WHY = "nuspace.kernel.why"


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


class Bracketed:
    """The kv passes over both stores, as a transform: the last rewrite a program gets (D23).

    One pass per store, each leaving the other's refs alone: Space, then
    States, whose refs are the rerooted state ones. A branch touching both
    gets a bracket of each, and a program's own bracket for one store is
    looked into by the other's pass.
    """

    __slots__ = ()

    def __call__(self, term: nu.Nu) -> nu.Nu:
        """``term`` with its Space and States reads and writes bracketed."""
        return nustd.kv.auto_flow_atomic(nustd.kv.auto_flow_atomic(term, scope=Space), scope=States)


def end_cell_run(
    run_id: nu.StrArg,
    cell_run_id: nu.StrArg,
    exit_: nu.StrArg,
    error: nu.StrArg | None = None,
    out: nu.Nu | None = None,
) -> nu.Nu:
    """A cell run's end: ``exit``, ``error``, ``terminated_at``, out of ``cells_running``. No bracket.

    Written once: a cell run already ended keeps the end it has. Shared by
    the body, which ends its own, and the kernel, which ends the ones whose
    worker died or whose plane run was killed.

    Args:
        run_id: The plane run.
        cell_run_id: The cell run.
        exit_: How it ended, one of :data:`~nuspace.shapes.EXITS`.
        error: Why, when there is something to say.
        out: What ``out`` is set to, when the writer has it.
    """
    row = _kernel.runs[run_id]
    cr = row.cells[cell_run_id]
    writes = cr.exit.set(exit_)
    if error is not None:
        writes = writes >> cr.error.set(error)
    if out is not None:
        writes = cr.out.set(out) >> writes
    writes = writes >> cr.terminated_at.set(Now())
    return nu.IfDo(nu.Not(cr.terminated_at.exists()), writes) >> nu.IfDo(
        row.cells_running.contains(cell_run_id), row.cells_running.discard(cell_run_id)
    )


def _mark_started(run_id: str, cell_run_id: str) -> nu.Nu:
    """``started_at``, stamped once."""
    cr = _kernel.runs[run_id].cells[cell_run_id]
    return atomic(nu.IfDo(nu.Not(cr.started_at.exists()), cr.started_at.set(Now())))


def _flush(run_id: str, cell_run_id: str) -> nu.Nu:
    """Write waiting output to the record, if there is any."""
    cr = _kernel.runs[run_id].cells[cell_run_id]
    out = nu.ObjectAttrRef(_OUT)
    return nu.IfDo(HasOut(), nu.Let(_OUT, TakeOut(), atomic(cr.out.set(out))))


def _finish(
    run_id: str,
    cell_run_id: str,
    exit_: nu.StrArg,
    *,
    error: nu.Nu | None = None,
    extra: nu.Nu | str = "",
) -> nu.Nu:
    """The last write: out flushed, exit, error, terminated_at, out of ``cells_running``. One commit."""
    why = None if error is None else nu.StrAttrRef(_WHY)
    commit = atomic(end_cell_run(run_id, cell_run_id, exit_, why, nu.ObjectAttrRef(_OUT)))
    # Texts are made before the bracket, which deep copies attrs and would
    # carry the caught exception in with it.
    if error is not None:
        commit = nu.Let(_WHY, error, commit)
    return nu.Let(_OUT, TakeOut(extra, final=True), commit)


def build_body(
    run_id: str,
    cell_run_id: str,
    plane: str,
    cell: str,
    envs: Sequence[Env] = (),
) -> nu.Nu:
    """One cell run's whole life on its worker, as a term to run there.

    Args:
        run_id: The plane run's store id.
        cell_run_id: The cell run's store id.
        plane: The plane id.
        cell: The cell id.
        envs: Resolved envs, outermost first. Their wraps are applied here,
            in the host, their rewrites ride along onto the worker.

    Returns:
        A picklable term. Binds :data:`~nuspace.ops.PLANE_ATTR`,
        :data:`~nuspace.ops.CELL_ATTR`, :data:`~nuspace.ops.RUN_ATTR` and
        :data:`~nuspace.ops.CELL_RUN_ATTR` for the program and its envs.
    """
    rewrite = Rewrites(
        Reroot(plane, cell),
        *(env.rewrite for env in envs if env.rewrite is not None),
        Bracketed(),
    )
    source = Space.planes[plane].cells[cell].prog
    load = nustd.kv.auto_flow_atomic(
        source.load(scope={"plane": plane, "cell": cell}, rewrite=rewrite), scope=Space
    )
    outcome = nu.StrAttrRef(_OUTCOME)
    # On the loop: a program that subscribes is async only.
    program = nu.ParallelAsync(nu.prog.Eval(load))
    asked = _kernel.runs[run_id].cells[cell_run_id].interrupt_requested
    interrupted = until(flag(asked, False), asked.on_change()) >> nu.SetCmd(
        outcome, nu.Str(EXIT_INTERRUPTED)
    )
    flusher = nu.ForeverDo(nu.Delay(FLUSH_SECONDS) >> _flush(run_id, cell_run_id))
    # The program winning leaves the outcome ok. The flusher never wins.
    run = nu.Let(
        _OUTCOME,
        nu.Str(EXIT_OK),
        _mark_started(run_id, cell_run_id)
        >> nu.Race(program, interrupted, flusher)
        >> _finish(run_id, cell_run_id, outcome),
    )
    for env in reversed(envs):
        if env.wrap is not None:
            run = env.wrap(run)
    # Outside the wraps, so an env failing to open is this cell run failing.
    failed = _finish(
        run_id,
        cell_run_id,
        EXIT_FAILED,
        error=ErrorText(nu.ObjectAttrRef(_ERROR)),
        extra=ErrorText(nu.ObjectAttrRef(_ERROR), full=True),
    )
    body = nu.With(Captured(), body=nu.TryCatch(run, catch=failed, error_key=_ERROR))
    ids = ((PLANE_ATTR, plane), (CELL_ATTR, cell), (RUN_ATTR, run_id), (CELL_RUN_ATTR, cell_run_id))
    for name, value in reversed(ids):
        body = nu.Let(name, nu.Str(value), body)
    return body
