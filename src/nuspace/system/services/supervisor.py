"""supervisor: restarts the cells its policy names, with backoff or a fixed delay (D13).

Acts only on cells listed in its own state (:class:`Policy`), so it never
fights another owner over a run. Per cell, when nothing of it is live and
its latest run ended in a way the policy covers, it waits a backoff and ups
the cell again the way the last run was upped: same envs, the same worker
while that worker is still serving other runs, else a fresh one.

=============  ===========================  =====================
policy         restarts after exit          never after
=============  ===========================  =====================
``on-failure`` ``failed``                   ``ok``, ``stopped``,
``always``     ``ok``, ``failed``           ``killed``
=============  ===========================  =====================

=============  =========================================================
wait           before each restart
=============  =========================================================
backoff        0.25s, doubled per restart after a failure, capped at 30s,
               back to 0.25s after an ``ok`` exit. The default
fixed delay    exactly the seconds given to :func:`supervise`, every time.
               ``always`` with a delay is a periodic cell
=============  =========================================================

``stopped`` and ``killed`` are somebody asking, so they are respected.
"""

from __future__ import annotations

import nu
import nustd.kv
from nuspace.ops import cell_exists, up, worker
from nuspace.ops.utils import atomic, fresh, or_else, text
from nuspace.shapes import (
    EXIT_FAILED,
    EXIT_OK,
    STATUS_DEAD,
    STATUS_STOPPING,
    CellState,
    Space,
    reroot,
)

from ..utils import snap, wake


__all__ = [
    "ALWAYS",
    "BACKOFF_CAP",
    "BACKOFF_START",
    "BY",
    "CELL",
    "ON_FAILURE",
    "PLANE",
    "POLICIES",
    "SHIM",
    "Policy",
    "delay_of",
    "policy_of",
    "program",
    "supervise",
    "unsupervise",
]


#: The plane id, fixed (D31).
PLANE = "supervisor"

#: The one cell on the plane.
CELL = "main"

#: What runs the supervisor starts are recorded as ``by``.
BY = "supervisor"

#: Restart after a failed exit only.
ON_FAILURE = "on-failure"

#: Restart after an ok or a failed exit.
ALWAYS = "always"

#: The policies a cell can be supervised under.
POLICIES = (ON_FAILURE, ALWAYS)

#: The first wait before a restart, in seconds.
BACKOFF_START = 0.25

#: The longest wait before a restart, in seconds.
BACKOFF_CAP = 30.0

#: The cell's prog: the code lives here, the store holds this (D20).
SHIM = """\
from nuspace.system.services import supervisor


def out():
    return supervisor.program()
"""

_kernel = Space.kernel

_KEY = "nuspace.supervisor.key"
_PLANE = "nuspace.supervisor.plane"
_CELL = "nuspace.supervisor.cell"
_DELAY = "nuspace.supervisor.delay"
_FIXED = "nuspace.supervisor.fixed"
_HANDLED = "nuspace.supervisor.handled"
_LATEST = "nuspace.supervisor.latest"
_WORKER = "nuspace.supervisor.worker"


class Policy(CellState):
    """The supervisor's state, keyed ``"<plane>/<cell>"``.

    ``cells`` holds each cell's policy in :data:`POLICIES`. ``delays`` holds
    the fixed wait in seconds of the cells that have one, in place of the
    backoff.
    """

    cells = nustd.kv.DictRef.slot(str)
    delays = nustd.kv.DictRef.slot(float)


def _key(plane_id: nu.StrArg, cell_id: nu.StrArg) -> nu.StrArg:
    if isinstance(plane_id, str) and isinstance(cell_id, str):
        return f"{plane_id}/{cell_id}"

    def part(x: nu.StrArg) -> nu.Nu:
        return nu.Str(x) if isinstance(x, str) else x

    return part(plane_id) + nu.Str("/") + part(cell_id)


def _here(term: nu.Nu) -> nu.Nu:
    """``term`` with :class:`Policy` landing at the supervisor's own cell."""
    return reroot(term, PLANE, CELL)


def _made() -> nu.Nu:
    """The policy dicts written empty if they never were, so a subscription on them resolves.

    Asks the cell's state for the keys: a dict never written reads as there.
    """
    state = Space.planes[PLANE].cells[CELL].state
    return nu.IfDo(
        nu.Not(state.contains("cells")), _here(Policy.cells.set(nu.Literal({})))
    ) >> nu.IfDo(nu.Not(state.contains("delays")), _here(Policy.delays.set(nu.Literal({}))))


def _drop(ref: nu.Nu, key: nu.StrArg) -> nu.Nu:
    """``key`` out of the dict at ``ref``. A no-op when it is not there."""
    return nu.IfDo(ref.contains(key), ref.del_item(key))


def supervise(
    plane_id: nu.StrArg,
    cell_id: nu.StrArg,
    policy: nu.StrArg = ON_FAILURE,
    delay: nu.FloatArg | None = None,
) -> nu.Nu:
    """Put a cell under the supervisor, or change its policy and delay.

    Args:
        plane_id: The cell's plane.
        cell_id: The cell.
        policy: :data:`ON_FAILURE` or :data:`ALWAYS`.
        delay: Seconds to wait before every restart, in place of the
            backoff. None clears it, back to the backoff.
    """
    key = _key(plane_id, cell_id)
    delays = Policy.delays
    timing = _drop(delays, key) if delay is None else delays.set_item(key, nu.ToFloat(delay))
    return atomic(_made() >> _here(Policy.cells.set_item(key, policy) >> timing))


def unsupervise(plane_id: nu.StrArg, cell_id: nu.StrArg) -> nu.Nu:
    """Take a cell off the supervisor, delay and all. Its live runs are left alone.

    A no-op when not listed.
    """
    key = _key(plane_id, cell_id)
    return atomic(_here(_drop(Policy.cells, key) >> _drop(Policy.delays, key)))


def policy_of(plane_id: nu.StrArg, cell_id: nu.StrArg) -> nu.Nu:
    """A cell's policy, from anywhere, ``""`` when it is not supervised. Bare read."""
    return _here(_policy(_key(plane_id, cell_id)))


def delay_of(plane_id: nu.StrArg, cell_id: nu.StrArg) -> nu.Nu:
    """A cell's fixed delay in seconds, from anywhere, -1 when it has none. Bare read."""
    return _here(_fixed(_key(plane_id, cell_id)))


# --- One cell ------------------------------------------------------------------


def _of_cell(ids: nu.Nu, plane: nu.StrArg, cell: nu.StrArg) -> nu.Nu:
    """The run ids in ``ids`` that ran ``plane``/``cell``, as a stream."""
    item = fresh("sup")
    run = _kernel.runs[nu.StrAttrRef(item)]
    same = nu.And(nu.Eq(text(run.plane), plane), nu.Eq(text(run.cell), cell))
    return nu.Filter(ids, same, key=item)


def _live(plane: nu.StrArg, cell: nu.StrArg) -> nu.Nu:
    """Whether any run of the cell is live."""
    ids = nu.List(nu.Collect(_of_cell(nu.list(_kernel.live.keys()), plane, cell)))
    return nu.Gt(ids.len(), nu.Int(0))


def _latest(plane: nu.StrArg, cell: nu.StrArg) -> nu.Nu:
    """The cell's newest run id, ``""`` when it has none. Minted ids sort by creation."""
    last = nu.Last(_of_cell(nu.list(_kernel.runs.keys()), plane, cell))
    return nu.If(nu.IsEmpty(last), nu.Str(""), last)


def _policy(key: nu.StrArg) -> nu.Nu:
    """The key's policy, ``""`` once it is gone (the fold cancels the arm a beat later)."""
    cells = Policy.cells
    return nu.If(cells.contains(key), nu.ToStr(cells[key]), nu.Str(""))


def _fixed(key: nu.StrArg) -> nu.Nu:
    """The key's fixed delay in seconds, -1 when it has none and backs off instead."""
    delays = Policy.delays
    return nu.If(delays.contains(key), nu.ToFloat(delays[key]), nu.Float(-1.0))


def _due(key: nu.StrAttrRef, plane: nu.StrArg, cell: nu.StrArg, latest: nu.StrAttrRef) -> nu.Nu:
    """Whether to restart: nothing live, the latest run new to us and dead the policy's way."""
    run = _kernel.runs[latest]
    exit_ = text(run.exit)
    covered = nu.Or(
        nu.Eq(exit_, nu.Str(EXIT_FAILED)),
        nu.And(nu.Eq(exit_, nu.Str(EXIT_OK)), nu.Eq(_policy(key), nu.Str(ALWAYS))),
    )
    return nu.And(
        nu.Ne(latest, nu.Str("")),
        nu.Ne(latest, nu.StrAttrRef(_HANDLED)),
        nu.Eq(text(run.status), nu.Str(STATUS_DEAD)),
        covered,
        cell_exists(plane, cell),
        nu.Not(_live(plane, cell)),
    )


def _serving(worker_id: nu.Nu) -> nu.Nu:
    """Whether a worker can take the restart: living, not stopping, and running something.

    A worker with nothing live is about to be idle collected (D9), so a run
    put on it would be killed with it.
    """
    item = fresh("sup_on")
    on = nu.List(
        nu.Collect(
            nu.Filter(
                nu.list(_kernel.live.keys()),
                nu.Eq(_kernel.live[nu.StrAttrRef(item)], worker_id),
                key=item,
            )
        )
    )
    return nu.And(
        _kernel.active.contains(worker_id),
        nu.Ne(text(_kernel.workers[worker_id].status), nu.Str(STATUS_STOPPING)),
        nu.Gt(on.len(), nu.Int(0)),
    )


def _restart(plane: nu.StrAttrRef, cell: nu.StrAttrRef, latest: nu.StrAttrRef) -> nu.Nu:
    """The cell up again as its latest run was: its envs, its worker if still serving."""
    run = _kernel.runs[latest]
    old = snap(text(run.worker))
    w = nu.StrAttrRef(_WORKER)
    # Envs read inside up's own commit, never bound: a list read on a worker
    # is a reference into the host, and a bracket deep copies what is bound.
    again = up(plane, nu.List.of(cell), worker=w, envs=or_else(run.envs, []), by=BY)
    return nu.IfDo(
        snap(_serving(text(run.worker))),
        nu.Let(_WORKER, old, again),
        nu.Let(_WORKER, worker(), again),
    )


def _turn(key: nu.StrAttrRef, plane: nu.StrAttrRef, cell: nu.StrAttrRef) -> nu.Nu:
    """One look: restart after the wait when due, else wait for ``live`` to move.

    The wait is the key's fixed delay when it has one, read as it is due,
    else the backoff.
    """
    latest = nu.StrAttrRef(_LATEST)
    delay = nu.FloatAttrRef(_DELAY)
    fixed = nu.FloatAttrRef(_FIXED)
    exit_ = text(_kernel.runs[latest].exit)
    doubled = delay * nu.Float(2.0)
    backoff = nu.Delay(delay) >> nu.SetCmd(
        delay, nu.If(nu.Gt(doubled, nu.Float(BACKOFF_CAP)), nu.Float(BACKOFF_CAP), doubled)
    )
    act = (
        nu.IfDo(snap(nu.Eq(exit_, nu.Str(EXIT_OK))), nu.SetCmd(delay, nu.Float(BACKOFF_START)))
        >> nu.SetCmd(nu.StrAttrRef(_HANDLED), latest)
        >> nu.Let(
            _FIXED,
            snap(_fixed(key)),
            nu.IfDo(nu.Ge(fixed, nu.Float(0.0)), nu.Delay(fixed), backoff),
        )
        # Read again after the wait: someone else may have upped it meanwhile.
        >> nu.IfDo(snap(nu.Not(_live(plane, cell))), _restart(plane, cell, latest))
    )
    return nu.Let(
        _LATEST,
        snap(_latest(plane, cell)),
        nu.IfDo(snap(_due(key, plane, cell, latest)), act, wake(_kernel.live.on_children_change())),
    )


def _arm(key: nu.StrAttrRef) -> nu.Nu:
    """One supervised cell, watched for as long as its key is listed."""
    parts = key.split("/", 1)
    plane, cell = nu.StrAttrRef(_PLANE), nu.StrAttrRef(_CELL)
    body = nu.Let(
        _DELAY,
        nu.Float(BACKOFF_START),
        nu.Let(_HANDLED, nu.Str(""), nu.ForeverDo(_turn(key, plane, cell))),
    )
    return nu.Let(_PLANE, nu.ToStr(parts[0]), nu.Let(_CELL, nu.ToStr(parts[1]), body))


def program() -> nu.Nu:
    """One arm per supervised cell, births and deaths included. Never returns."""
    cells = Policy.cells
    return atomic(_made()) >> nu.ForEachParReactive(
        snap(nu.list(cells.keys())),
        snap(cells.on_children_change()),
        _arm(nu.StrAttrRef(_KEY)),
        _KEY,
    )
