"""supervisor: keeps the planes its policy names running, with backoff or a fixed delay (D13).

Plane level, and only its own runs. Per supervised plane (:class:`Policy`)
it keeps one live plane run ``by`` supervisor, and remembers its id in its
own state. It only ever reads that run, by id, and never looks at or touches
a run somebody else started: nav's tab runs of the same plane are theirs.

    none of its runs yet       plane_run(plane, by=supervisor), no wait
    its run live               wait for it to end
    its run ended              restart per policy on the run's exit, after
                                 the wait, else leave the plane down until it
                                 is supervised again
    unsupervised               forgotten, and its run stopped

=============  ===========================  =====================
policy         restarts after exit          never after
=============  ===========================  =====================
``on-failure`` ``failed``                   ``ok``, ``interrupted``,
``always``     ``ok``, ``failed``           ``killed``
=============  ===========================  =====================

=============  =========================================================
wait           before each restart
=============  =========================================================
backoff        0.25s, doubled per restart after a failure, capped at 30s,
               back to 0.25s after an ``ok`` exit. The default
fixed delay    exactly the seconds given to :func:`supervise`, every time.
               ``always`` with a delay is a periodic plane
=============  =========================================================

``interrupted`` and ``killed`` are somebody asking, so they are respected.
A cell failing inside a run that is still live is left alone: the plane
run is what the supervisor restarts, once it has ended.

Every read is a point read: a policy, a run id, a run's ``exit``. Nothing
walks ``runs``, ``running`` or a run's cell runs.
"""

from __future__ import annotations

import nu
import nustd.kv
from nuspace.ops import plane_exists, plane_stop
from nuspace.ops.kernel import add_plane_run
from nuspace.ops.utils import MintId, atomic, atomic_state, fresh, text
from nuspace.shapes import EXIT_FAILED, EXIT_OK, CellState, Space, States, reroot

from ..utils import Ticking, moved, park, snap, until, wake


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
    "run_of",
    "supervise",
    "unsupervise",
]


#: The plane id, fixed (D31).
PLANE = "supervisor"

#: The one cell on the plane.
CELL = "main"

#: What plane runs the supervisor starts are recorded as ``by``.
BY = "supervisor"

#: Restart after a failed exit only.
ON_FAILURE = "on-failure"

#: Restart after an ok or a failed exit.
ALWAYS = "always"

#: The policies a plane can be supervised under.
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

_PLANE = "nuspace.supervisor.plane"


class _Arm(nu.Shape):
    """What one supervised plane's arm keeps across its turns: the backoff it waits next."""

    delay = nu.FloatRef.slot()


class Policy(CellState):
    """The supervisor's state, keyed by plane id.

    ``planes`` holds each supervised plane's policy in :data:`POLICIES`.
    ``delays`` holds the fixed wait in seconds of the planes that have one,
    in place of the backoff. ``runs`` holds the plane run the supervisor
    last started for each, live or ended: the only run it ever looks at.
    """

    planes = nustd.kv.DictRef.slot(str)
    delays = nustd.kv.DictRef.slot(float)
    runs = nustd.kv.DictRef.slot(str)


def _here(term: nu.Nu) -> nu.Nu:
    """``term`` with :class:`Policy` landing at the supervisor's own cell."""
    return reroot(term, PLANE, CELL)


def _made() -> nu.Nu:
    """The policy dicts written empty if they never were, so a subscription on them resolves.

    Asks the cell's state for the keys: a dict never written reads as there.
    """
    state = States.planes[PLANE].cells[CELL]
    writes = [
        nu.IfDo(nu.Not(state.contains(name)), _here(ref.set(nu.Literal({}))))
        for name, ref in (
            ("planes", Policy.planes),
            ("delays", Policy.delays),
            ("runs", Policy.runs),
        )
    ]
    return writes[0] >> writes[1] >> writes[2]


def _drop(ref: nu.Nu, key: nu.StrArg) -> nu.Nu:
    """``key`` out of the dict at ``ref``. A no-op when it is not there."""
    return nu.IfDo(ref.contains(key), ref.del_item(key))


def _policy(plane: nu.StrArg) -> nu.Nu:
    """The plane's policy, ``""`` when it is not supervised."""
    planes = Policy.planes
    return nu.If(planes.contains(plane), nu.ToStr(planes[plane]), nu.Str(""))


def _fixed(plane: nu.StrArg) -> nu.Nu:
    """The plane's fixed delay in seconds, -1 when it has none and backs off instead."""
    delays = Policy.delays
    return nu.If(delays.contains(plane), nu.ToFloat(delays[plane]), nu.Float(-1.0))


def _mine(plane: nu.StrArg) -> nu.Nu:
    """The plane run the supervisor last started for the plane, ``""`` when none."""
    runs = Policy.runs
    return nu.If(runs.contains(plane), nu.ToStr(runs[plane]), nu.Str(""))


def supervise(
    plane_id: nu.StrArg, policy: nu.StrArg = ON_FAILURE, delay: nu.FloatArg | None = None
) -> nu.Nu:
    """Put a plane under the supervisor, or change its policy and delay. One commit.

    A plane whose supervisor run ended and was not restarted (interrupted,
    killed, or ``ok`` under ``on-failure``) is brought up again: supervising
    it is asking for it to run.

    Args:
        plane_id: The plane.
        policy: :data:`ON_FAILURE` or :data:`ALWAYS`.
        delay: Seconds to wait before every restart, in place of the
            backoff. None clears it, back to the backoff.
    """
    delays = Policy.delays
    timing = (
        _drop(delays, plane_id) if delay is None else delays.set_item(plane_id, nu.ToFloat(delay))
    )
    run = _mine(plane_id)
    over = nu.And(nu.Ne(run, nu.Str("")), nu.Not(_kernel.running.contains(run)))
    return atomic_state(
        _made()
        >> _here(
            Policy.planes.set_item(plane_id, policy)
            >> timing
            >> nu.IfDo(over, _drop(Policy.runs, plane_id))
        )
    )


def unsupervise(plane_id: nu.StrArg) -> nu.Nu:
    """Take a plane off the supervisor, delay and all, and stop the run it started.

    Forgotten in one commit, so the supervisor starts nothing for it after;
    then its run, if live, is stopped: interrupted, killed after the grace.
    Returns once it has ended, or once the kill is asked for. A no-op when
    the plane is not supervised.

    The remembered run id stays: the commit that cancels the plane's arm
    must not also wake it, or on Python 3.11 the cancel can be lost (a
    ``Timeout`` whose body completes as it is cancelled swallows it) and
    the fold waits on the arm forever. :func:`supervise` and the next open
    drop it.
    """
    forget = _here(_drop(Policy.planes, plane_id) >> _drop(Policy.delays, plane_id))

    def stop(held: nu.ObjectRef) -> nu.Nu:
        run = nu.Str(held)
        live = nu.And(nu.Ne(run, nu.Str("")), _kernel.running.contains(run))
        return nu.IfDo(snap(live), plane_stop(run))

    return atomic_state(forget) >> nu.let(snap(_here(_mine(plane_id))), stop)


def policy_of(plane_id: nu.StrArg) -> nu.Nu:
    """A plane's policy, from anywhere, ``""`` when it is not supervised. Bare read."""
    return _here(_policy(plane_id))


def delay_of(plane_id: nu.StrArg) -> nu.Nu:
    """A plane's fixed delay in seconds, from anywhere, -1 when it has none. Bare read."""
    return _here(_fixed(plane_id))


def run_of(plane_id: nu.StrArg) -> nu.Nu:
    """The plane run the supervisor last started for a supervised plane, from anywhere. Bare read.

    ``""`` when it has none, or the plane is not supervised.
    """
    return _here(nu.If(nu.Eq(_policy(plane_id), nu.Str("")), nu.Str(""), _mine(plane_id)))


# --- One plane -----------------------------------------------------------------


def _start(plane: nu.Str, mine: nu.Str) -> nu.Nu:
    """A new plane run of the plane, ``by`` supervisor, then remembered.

    Written only while the plane is still supervised and its remembered run
    is still ``mine``: an unsupervise or a supervise landing first wins, so
    nothing is started that nobody tracks. A plane not there yet is waited
    for.

    The run is a Space commit and remembering it a States one, run first so
    the remembered id always names a run. The check is made again in the
    second: one of them landing in between refuses it, and the run just
    started, now tracked by nobody, is stopped.
    """
    still = nu.And(
        nu.Ne(_policy(plane), nu.Str("")), nu.Eq(_mine(plane), mine), plane_exists(plane)
    )

    def write(minted: nu.ObjectRef) -> nu.Nu:
        new = nu.Str(minted)
        start = atomic(nu.IfDo(still, add_plane_run(new, plane, by=BY)))
        made = _kernel.runs.contains(new)
        remember = atomic_state(nu.IfDo(nu.And(made, still), Policy.runs.set_item(plane, new)))
        orphan = nu.And(made, nu.Ne(_mine(plane), new))
        return start >> remember >> nu.IfDo(snap(orphan), plane_stop(new))

    return nu.IfDo(
        snap(plane_exists(plane)),
        nu.let(MintId("r"), write),
        wake(Space.planes.on_children_change()),
    )


def _covered(plane: nu.Str, exit_: nu.Nu) -> nu.Nu:
    """Whether the plane's policy restarts after ``exit_``."""
    return nu.Or(
        nu.Eq(exit_, nu.Str(EXIT_FAILED)),
        nu.And(nu.Eq(exit_, nu.Str(EXIT_OK)), nu.Eq(_policy(plane), nu.Str(ALWAYS))),
    )


def _wait() -> nu.Nu:
    """The wait before a restart: the fixed delay, read as it is due, else the backoff, doubled after."""
    plane = nu.Str(nu.Attr(_PLANE))
    delay = _Arm.delay
    doubled = delay * nu.Float(2.0)
    backoff = nu.Delay(delay) >> delay.set(
        nu.If(nu.Gt(doubled, nu.Float(BACKOFF_CAP)), nu.Float(BACKOFF_CAP), doubled)
    )

    def wait(held: nu.ObjectRef) -> nu.Nu:
        fixed = nu.Float(held)
        return nu.IfDo(nu.Ge(fixed, nu.Float(0.0)), nu.Delay(fixed), backoff)

    return nu.let(snap(_fixed(plane)), wait)


def _ended(plane: nu.Str, mine: nu.Str) -> nu.Nu:
    """Its run is over: restarted after the wait when the policy covers the exit.

    Otherwise left down, until its remembered run moves (supervised again).
    """
    exit_ = text(_kernel.runs[mine].exit)
    again = (
        nu.IfDo(snap(nu.Eq(exit_, nu.Str(EXIT_OK))), _Arm.delay.set(nu.Float(BACKOFF_START)))
        >> _wait()
        >> _start(plane, mine)
    )
    return nu.IfDo(snap(_covered(plane, exit_)), again, moved(Policy.runs[plane], mine))


def _turn(plane: nu.Str) -> nu.Nu:
    """One look at the plane's own run: start one, wait for it to end, or act on how it ended.

    A plane no longer supervised parks until the fold cancels the arm, so
    the loop never spins on a start its commit refuses.
    """
    running = _kernel.running

    def look(held: nu.ObjectRef) -> nu.Nu:
        mine = nu.Str(held)
        live = until(nu.Not(running.contains(mine)), running.on_children_change())
        return nu.IfDo(
            nu.Eq(mine, nu.Str("")),
            _start(plane, mine),
            nu.IfDo(snap(running.contains(mine)), live, _ended(plane, mine)),
        )

    return nu.IfDo(
        snap(nu.Eq(_policy(plane), nu.Str(""))), park(), nu.let(snap(_mine(plane)), look)
    )


def _arm(plane: nu.Str) -> nu.Nu:
    """One supervised plane, kept up for as long as it is listed."""
    return nu.Frame(_Arm, nu.ForeverDo(_turn(plane)), delay=nu.Float(BACKOFF_START))


def _forget_ended() -> nu.Nu:
    """Every remembered run no longer live, or of a plane no longer supervised, dropped.

    O(planes supervised since the last open). At open, reconcile ended every
    run the last open left, ``killed``: the supervisor starts its planes
    again rather than reading that as a request.
    """
    item = fresh("sup_forget")
    plane = nu.Str(nu.Attr(item))
    runs = Policy.runs
    over = nu.Or(
        nu.Not(Policy.planes.contains(plane)),
        nu.Not(_kernel.running.contains(nu.ToStr(runs[plane]))),
    )
    return nu.ForEachDo(nu.list(runs.keys()), nu.IfDo(over, runs.del_item(plane)), item=item)


def program() -> nu.Nu:
    """One arm per supervised plane, births and deaths included. Never returns."""
    planes = Policy.planes
    return atomic_state(_made() >> _forget_ended()) >> nu.ForEachParReactive(
        snap(nu.list(planes.keys())),
        Ticking(snap(planes.on_children_change())),
        _arm(nu.Str(nu.Attr(_PLANE))),
        _PLANE,
    )
