"""The body of one run: built in the host, dispatched into a worker, run there.

Everything a run is, as one Nu term with its ids baked in as plain strs::

    Let(plane, cell, run ids)
      With(Captured)                       out, attributed to this run
        TryCatch(                          raised: exit failed, error, traceback
          envs' wraps, space-wide outermost
            mark up
            Race(program, stop watch, out flusher)
            exit ok, or stopped when the watch won

The program is loaded in the worker from the store, so a run always runs
the prog as it is now. Its term is rewritten on the way in: reroot first,
then each env's rewrite, then the kv bracket (D23: a state ref only belongs
to Space once rerooted). The kernel's own record writes are short
transactions of their own, never held open while the program runs.

A run stops itself (D5): nothing in the host holds its task, so the body
watches its own ``status`` and leaves when it reads ``stopping``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nu.prog
import nustd.kv
from nuspace.ops import CELL_ATTR, PLANE_ATTR, RUN_ATTR
from nuspace.ops.utils import atomic, text
from nuspace.shapes import (
    EXIT_FAILED,
    EXIT_OK,
    EXIT_STOPPED,
    STATUS_DEAD,
    STATUS_STARTING,
    STATUS_STOPPING,
    STATUS_UP,
    Reroot,
    Space,
)

from .out import Captured, ErrorText, HasOut, TakeOut
from .utils import Now, snap


if TYPE_CHECKING:
    from collections.abc import Sequence

    from nu.tree import Transform

    from .envs import Env


__all__ = [
    "FLUSH_SECONDS",
    "WATCH_SECONDS",
    "Bracketed",
    "Rewrites",
    "build_body",
    "until",
]


#: How often a run's waiting output is written to its record.
FLUSH_SECONDS = 1.0

#: How long a status watch trusts its subscription before reading again. A
#: change landing between a read and the subscribe is caught this late.
WATCH_SECONDS = 1.0

_kernel = Space.kernel

# One body per context: a dispatch carries attrs, so the worker runs each
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
    """The kv pass over Space, as a transform: the last rewrite a program gets (D23)."""

    __slots__ = ()

    def __call__(self, term: nu.Nu) -> nu.Nu:
        """``term`` with its Space reads and writes bracketed."""
        return nustd.kv.auto_flow_atomic(term, scope=Space)


def until(ref: nu.Nu, value: str) -> nu.Nu:
    """Wait until the str at ``ref`` reads ``value``. Returns at once if it does.

    Waits on the ref's change subscription, read again at least every
    :data:`WATCH_SECONDS`, so a change landing between the read and the
    subscribe is late rather than lost.
    """
    wake = nu.Timeout(WATCH_SECONDS, nu.React(snap(ref.on_change())), on_timeout=nu.Delay(0.0))
    return nu.WhileDo(nu.Ne(snap(text(ref)), nu.Str(value)), wake)


def _mark_up(run_id: str) -> nu.Nu:
    """``starting -> up``, stamped. Left alone if ``down`` got there first."""
    row = _kernel.runs[run_id]
    return atomic(
        nu.IfDo(
            nu.Eq(text(row.status), nu.Str(STATUS_STARTING)),
            row.status.set(STATUS_UP) >> row.started.set(Now()),
        )
    )


def _flush(run_id: str) -> nu.Nu:
    """Write waiting output to the record, if there is any."""
    row = _kernel.runs[run_id]
    out = nu.AnyAttrRef(_OUT)
    return nu.IfDo(HasOut(), nu.Let(_OUT, TakeOut(), atomic(row.out.set(out))))


def _finish(
    run_id: str,
    exit_: nu.StrArg,
    *,
    error: nu.Nu | None = None,
    extra: nu.Nu | str = "",
) -> nu.Nu:
    """The last write: out flushed, exit, error, dead, ended, out of ``live``. One commit."""
    row = _kernel.runs[run_id]
    writes = row.out.set(nu.AnyAttrRef(_OUT)) >> row.exit.set(exit_)
    if error is not None:
        writes = writes >> row.error.set(nu.StrAttrRef(_WHY))
    writes = (
        writes
        >> row.status.set(STATUS_DEAD)
        >> row.ended.set(Now())
        >> nu.IfDo(_kernel.live.contains(run_id), _kernel.live.del_item(run_id))
    )
    # Texts are made before the bracket, which deep copies attrs and would
    # carry the caught exception in with it.
    commit = atomic(writes)
    if error is not None:
        commit = nu.Let(_WHY, error, commit)
    return nu.Let(_OUT, TakeOut(extra, final=True), commit)


def build_body(run_id: str, plane: str, cell: str, envs: Sequence[Env] = ()) -> nu.Nu:
    """One run's whole life in its worker, as a term to dispatch.

    Args:
        run_id: The run's store id.
        plane: The plane id.
        cell: The cell id.
        envs: Resolved envs, outermost first. Their wraps are applied here,
            in the host, their rewrites ride along into the worker.

    Returns:
        A picklable term. Binds :data:`~nuspace.ops.PLANE_ATTR`,
        :data:`~nuspace.ops.CELL_ATTR` and :data:`~nuspace.ops.RUN_ATTR`
        for the program and its envs.
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
    stop = until(_kernel.runs[run_id].status, STATUS_STOPPING) >> nu.SetCmd(
        outcome, nu.Str(EXIT_STOPPED)
    )
    flusher = nu.ForeverDo(nu.Delay(FLUSH_SECONDS) >> _flush(run_id))
    # The program winning leaves the outcome ok. The flusher never wins.
    run = nu.Let(
        _OUTCOME,
        nu.Str(EXIT_OK),
        _mark_up(run_id) >> nu.Race(program, stop, flusher) >> _finish(run_id, outcome),
    )
    for env in reversed(envs):
        if env.wrap is not None:
            run = env.wrap(run)
    # Outside the wraps, so an env failing to open is this run failing.
    failed = _finish(
        run_id,
        EXIT_FAILED,
        error=ErrorText(nu.AnyAttrRef(_ERROR)),
        extra=ErrorText(nu.AnyAttrRef(_ERROR), full=True),
    )
    body = nu.With(Captured(), body=nu.TryCatch(run, catch=failed, error_key=_ERROR))
    return nu.Let(
        PLANE_ATTR,
        nu.Str(plane),
        nu.Let(CELL_ATTR, nu.Str(cell), nu.Let(RUN_ATTR, nu.Str(run_id), body)),
    )
