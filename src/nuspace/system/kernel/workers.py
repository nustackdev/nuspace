"""The worker fold: one arm per living worker, in the host, where the pool is.

Beside it, :func:`orphans` fails runs asked of a worker that is gone.

An arm makes its worker true and keeps it true::

    starting  take a spare (local only), write wid, up
    then race
      (a) Wait for the process to exit, Kill to drop the handle, reap
      (b) watch status: stopping -> Kill, and (a) reaps
      (c) fold over this worker's live runs: dispatch each once
      (d) idle GC: had runs, has none -> stopping (D9), unless held (D40)

(a) is the only arm that ends, so the race ends when the process is gone,
however it went. ``Wait`` starts with the race, before anything can
``Kill`` (D25).

Reaping: the worker goes dead and out of ``active``, each of its live runs
goes dead and out of ``live``. A run's exit says who wanted it: ``stopped``
if the run was stopping, ``killed`` if its worker was, ``failed`` if nobody
asked (a crash).
"""

from __future__ import annotations

import nu
import nustd.mp_pool
from nuspace.ops import kill_worker
from nuspace.ops.utils import atomic, flag, fresh, text
from nuspace.shapes import (
    EXIT_FAILED,
    EXIT_KILLED,
    EXIT_STOPPED,
    KIND_LOCAL,
    STATUS_DEAD,
    STATUS_STARTING,
    STATUS_STOPPING,
    STATUS_UP,
    Space,
)
from nustd.mp_pool.presets import TakeSpare

from .body import until
from .dispatch import DispatchRun
from .out import ErrorText
from .utils import Now, park, snap


__all__ = ["WORKER_ATTR", "orphans", "worker_arm", "worker_fold"]


#: What the fold binds each worker id under.
WORKER_ATTR = "nuspace.kernel.worker"

_kernel = Space.kernel
_pool = nustd.mp_pool.PoolRef()

# Per arm names. Each fold arm runs on a context branch of its own, so one
# name serves every arm.
_WID = "nuspace.kernel.wid"
_CODE = "nuspace.kernel.code"
_SEEN = "nuspace.kernel.seen"
_MINE = "nuspace.kernel.mine"
_ERROR = "nuspace.kernel.error"
_WHY = "nuspace.kernel.why"


def _on(worker: nu.StrArg) -> nu.Nu:
    """Ids of the live runs on ``worker``. Unbracketed."""
    item = fresh("on")
    return nu.List(
        nu.Collect(
            nu.Filter(
                nu.list(_kernel.live.keys()),
                nu.Eq(_kernel.live[nu.StrAttrRef(item)], worker),
                key=item,
            )
        )
    )


def _reap(worker: nu.StrArg, error: nu.Nu) -> nu.Nu:
    """The worker and its live runs, dead. One commit. Unbracketed parts, bracketed whole.

    Runs are reaped before the worker's own status moves, since their exit
    reads whether the worker was stopping.
    """
    row = _kernel.workers[worker]
    item = fresh("reap")
    rid = nu.StrAttrRef(item)
    run = _kernel.runs[rid]
    asked = nu.Eq(text(row.status), nu.Str(STATUS_STOPPING))
    exit_ = nu.If(
        nu.Eq(text(run.status), nu.Str(STATUS_STOPPING)),
        nu.Str(EXIT_STOPPED),
        nu.If(asked, nu.Str(EXIT_KILLED), nu.Str(EXIT_FAILED)),
    )
    runs = nu.ForEachDo(
        _on(worker),
        nu.IfDo(nu.Ne(text(run.status), nu.Str(STATUS_STOPPING)), run.error.set(error))
        >> run.exit.set(exit_)
        >> run.status.set(STATUS_DEAD)
        >> run.ended.set(Now())
        >> _kernel.live.del_item(rid),
        item=item,
    )
    own = (
        nu.IfDo(nu.Not(nu.Eq(text(row.status), nu.Str(STATUS_STOPPING))), row.error.set(error))
        >> row.status.set(STATUS_DEAD)
        >> row.ended.set(Now())
        >> nu.IfDo(_kernel.active.contains(worker), _kernel.active.del_item(worker))
    )
    return atomic(runs >> own)


def _start(worker: nu.StrArg) -> nu.Nu:
    """``starting``: a local worker takes a spare and goes up, any other kind goes dead."""
    row = _kernel.workers[worker]
    wid = nu.IntAttrRef(_WID)
    # Conditional: a kill_worker landing while the spare was taken leaves the
    # worker stopping, and the race below kills it.
    take = nu.Let(
        _WID,
        TakeSpare(),
        atomic(
            row.wid.set(wid)
            >> row.started.set(Now())
            >> nu.IfDo(nu.Eq(text(row.status), nu.Str(STATUS_STARTING)), row.status.set(STATUS_UP))
        ),
    )
    refuse = _reap(worker, nu.Str("no worker of kind ") + text(row.kind))
    failed = nu.Let(
        _WHY,
        nu.Str("worker failed to start: ") + ErrorText(nu.AnyAttrRef(_ERROR)),
        _reap(worker, nu.StrAttrRef(_WHY)),
    )
    return nu.IfDo(
        nu.Eq(snap(text(row.status)), nu.Str(STATUS_STARTING)),
        nu.TryCatch(
            nu.IfDo(nu.Eq(snap(text(row.kind)), nu.Str(KIND_LOCAL)), take, refuse),
            catch=failed,
            error_key=_ERROR,
        ),
    )


def _run_arm(run_id: nu.StrArg, wid: nu.IntArg) -> nu.Nu:
    """One live run on this worker: dispatched once while ``starting``, then parked.

    A run already ``stopping`` here was downed before it was ever dispatched,
    so the host writes its end itself. A dispatch that raises (an unknown
    env, a worker gone) is the run failing.
    """
    run = _kernel.runs[run_id]

    def end(exit_: nu.StrArg, error: nu.Nu | None = None) -> nu.Nu:
        writes = run.exit.set(exit_)
        if error is not None:
            writes = writes >> run.error.set(nu.StrAttrRef(_WHY))
        commit = atomic(
            writes
            >> run.status.set(STATUS_DEAD)
            >> run.ended.set(Now())
            >> nu.IfDo(_kernel.live.contains(run_id), _kernel.live.del_item(run_id))
        )
        return commit if error is None else nu.Let(_WHY, error, commit)

    dispatch = nu.TryCatch(
        DispatchRun(run_id, wid),
        catch=end(EXIT_FAILED, ErrorText(nu.AnyAttrRef(_ERROR))),
        error_key=_ERROR,
    )
    return (
        nu.SwitchDo(
            snap(text(run.status)),
            {STATUS_STARTING: dispatch, STATUS_STOPPING: end(EXIT_STOPPED)},
            nu.Noop(),
        )
        >> park()
    )


def _idle(worker: nu.StrArg) -> nu.Nu:
    """One idle check: no live runs, and it has had one, so ask it to stop (D9).

    ``_SEEN`` remembers a run was seen live on it. A run that came and went
    between two checks is found by scanning the history, only while nothing
    was seen yet.
    """
    mine = nu.IntAttrRef(_MINE)
    seen = nu.BoolAttrRef(_SEEN)
    item = fresh("idle")
    had = nu.Gt(
        nu.List(
            nu.Collect(
                nu.Filter(
                    nu.list(_kernel.runs.keys()),
                    nu.Eq(text(_kernel.runs[nu.StrAttrRef(item)].worker), worker),
                    key=item,
                )
            )
        ).len(),
        nu.Int(0),
    )
    return nu.Let(
        _MINE,
        snap(_on(worker).len()),
        nu.IfDo(nu.Gt(mine, nu.Int(0)), nu.SetCmd(seen, nu.Bool(True)))
        >> nu.IfDo(
            nu.Eq(mine, nu.Int(0)),
            nu.IfDo(seen, kill_worker(worker), nu.IfDo(snap(had), kill_worker(worker))),
        ),
    )


def worker_arm(worker: nu.StrArg) -> nu.Nu:
    """One worker's whole life in the host. Ends only by the fold cancelling it."""
    row = _kernel.workers[worker]
    wid = nu.IntAttrRef(_WID)
    reap = nu.Let(
        _CODE,
        _pool.wait(wid),
        _pool.kill(wid)
        >> _reap(worker, nu.Str("worker exited: ") + nu.ToStr(nu.AnyAttrRef(_CODE))),
    )
    stop = until(row.status, STATUS_STOPPING) >> _pool.kill(wid) >> park()
    item = fresh("runs")
    runs = nu.ForEachParReactive(
        snap(_on(worker)),
        snap(_kernel.live.on_children_change()),
        _run_arm(nu.StrAttrRef(item), wid),
        item,
    )
    # Held is written with the worker, so one read says it for life.
    idle = nu.IfDo(
        snap(flag(row.held, False)),
        park(),
        _idle(worker) >> nu.ReactForever(snap(_kernel.live.on_children_change()), _idle(worker)),
    )
    alive = nu.Let(
        _WID,
        snap(row.wid),
        nu.Let(_SEEN, nu.Bool(False), nu.Race(reap, stop, runs, idle)),
    )
    up = nu.And(nu.Ne(snap(text(row.status)), nu.Str(STATUS_DEAD)), snap(row.wid.exists()))
    # Not up and not dead: stopping before a spare was taken. Nothing to kill.
    gone = nu.IfDo(
        nu.Ne(snap(text(row.status)), nu.Str(STATUS_DEAD)),
        _reap(worker, nu.Str("worker stopped before it started")),
    )
    return _start(worker) >> nu.IfDo(up, alive, gone) >> park()


def orphans() -> nu.Nu:
    """Fail every live run whose worker is not living. Now, and on every change to ``live``.

    ``up`` does not check its worker, so a run can land on one that died
    first (eg idle GC'd between a ``down`` and an ``up``). Nothing would ever
    dispatch it, so it fails here with the reason.
    """
    item = fresh("orphan")
    rid = nu.StrAttrRef(item)
    run = _kernel.runs[rid]
    owner = _kernel.live[rid]

    def sweep() -> nu.Nu:
        return atomic(
            nu.ForEachDo(
                nu.list(_kernel.live.keys()),
                nu.IfDo(
                    nu.Not(_kernel.active.contains(owner)),
                    run.error.set(nu.Str("worker is not running: ") + nu.ToStr(owner))
                    >> run.exit.set(EXIT_FAILED)
                    >> run.status.set(STATUS_DEAD)
                    >> run.ended.set(Now())
                    >> _kernel.live.del_item(rid),
                ),
                item=item,
            )
        )

    return sweep() >> nu.ReactForever(snap(_kernel.live.on_children_change()), sweep())


def worker_fold() -> nu.Nu:
    """:func:`worker_arm` for every worker in ``active``, births and deaths included.

    The containers must exist before this subscribes (reconcile makes them).
    """
    item = WORKER_ATTR
    return nu.ForEachParReactive(
        snap(nu.list(_kernel.active.keys())),
        snap(_kernel.active.on_children_change()),
        worker_arm(nu.StrAttrRef(item)),
        item,
    )
