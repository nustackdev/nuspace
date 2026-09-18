"""One Cell executing, under its own ``restart`` and ``reload``.

A Cell is the only thing in a Space that runs, and it never runs in the main
process. :func:`cell_body` is the term whatever process hosts the Cell
evaluates: the program read from the store, run, and started again or left
stopped the way ``restart`` says. Both exec modes ship exactly that term; they
differ in which process it lands in.

The two props sit on different sides of that line, and the split is not
arbitrary:

- ``restart`` is about the program ending, so it belongs where the program
  runs. A dispatched body has no waiter and its outcome is dropped, so main
  can tell neither that a Cell ended nor whether it raised. The process
  holding the program can tell both.
- ``reload`` is about the program changing, so it belongs where the
  granularity is. :func:`cell_arm` cancels the run and loads again in the same
  process, which is what ``async`` wants, since killing would take the Plane's
  other Cells down too. :func:`cell_dispatch` kills the process and dispatches
  into a fresh one, which is what ``mp`` wants, since a Cell that owns a
  process should get a clean one when its code changes.

Nothing here raises. A Cell that fails writes the failure to its own ``error``
and stays where it is, because an error out of a dispatched body reaches
nobody and an error out of a fold arm ends the arm silently. ``error`` holds
the last failure, or the empty string once a turn has gone through without
one, so a reader asks whether it is empty rather than whether it is there.

A Cell's program is a python module whose ``out`` declares the ids it wants:
``def out(plane, cell)``, either name or neither. Where it lives is the only
thing nuspace tells it.
"""

from __future__ import annotations

import nu
import nu.prog
import nustd.kv
import nustd.mp_pool
from nuspace.exec.utils import park, prop, reenters_on
from nuspace.shapes import (
    DEFAULT_RELOAD,
    DEFAULT_RESTART,
    RESTART_ALWAYS,
    RESTART_ON_FAILURE,
    Space,
)


__all__ = [
    "BACKOFF_SECONDS",
    "BACKOFF_STEPS",
    "CELL_ATTR",
    "cell_arm",
    "cell_body",
    "cell_dispatch",
]


#: What a Cell fold binds each Cell id under. Every arm gets its own Context
#: branch, so one name serves every Cell and no caller has to namespace it.
CELL_ATTR = "cell"

#: How long the first restart waits. Every one after a failure that follows
#: it waits twice as long as the last.
BACKOFF_SECONDS = 0.25

#: Where the doubling stops, counted in consecutive failures. At the default
#: base that is a shade over half a minute between attempts, which is slow
#: enough to stop a broken Cell heating the process and fast enough that a
#: fixed one comes back while somebody is still watching.
BACKOFF_STEPS = 7

#: How many turns this arm has taken since the last one that ended cleanly.
#: An attr rather than anything in a fabric: the fold gives each arm its own
#: attrs key space, so one name is one counter per Cell with nothing to key
#: by, and a Cell's program cannot reach a name it does not know. It survives
#: the turn because a storage bracket restores the Context it swapped, and
#: the writes below sit outside every bracket the atomicity pass places.
_ATTEMPT_ATTR = "nuspace.cell.attempt"

#: The pool worker running this Cell, while ``mp`` is running it.
_WORKER_ATTR = "nuspace.cell.worker"


def _attempt() -> nu.Nu:
    """This arm's consecutive turn count."""
    return nu.IntAttrRef(_ATTEMPT_ATTR)


def _backoff() -> nu.Nu:
    """Wait before going round again, doubling per consecutive failure.

    Bounded twice over: the exponent stops at :data:`BACKOFF_STEPS`, and a
    turn that ended cleanly has reset the count, so a Cell that runs and
    returns keeps coming back at the base rate however long it failed before.
    """
    capped = nu.If(nu.Gt(_attempt(), nu.Int(BACKOFF_STEPS)), nu.Int(BACKOFF_STEPS), _attempt())
    steps = nu.If(nu.Gt(capped, nu.Int(0)), capped - nu.Int(1), nu.Int(0))
    return nu.Delay(nu.Float(BACKOFF_SECONDS) * nu.Pow(nu.Float(2.0), nu.ToFloat(steps)))


def cell_body(plane: nu.StrArg, *, root: type[nu.Shape] = Space) -> nu.Nu:
    """One Cell running under its ``restart`` policy, where the Cell is hosted.

    The Cell arrives as the attr :data:`CELL_ATTR`, so one term serves every
    Cell in a Plane: in ``async`` the fold binds it, in ``mp`` the dispatch
    carries it. Each turn reads the program again, so a restart picks up
    whatever the store holds now.

    ``restart`` is read per turn rather than at fan out, and the branch that
    decides is the one that already knows how the turn went. A turn that
    stops parks rather than returns: the fold above sweeps arms whose task
    ended and starts them again the next time a Cell is added or removed, so
    a Cell that ran once would silently run twice.

    Args:
        plane: the Plane this Cell is in. A term, since in ``async`` it
            arrives in the worker as a carried attr.
        root: the Space shape class this Cell is stored under.
    """
    cell = nu.StrAttrRef(CELL_ATTR)
    cells = root.planes[plane].cells
    row = cells[cell]
    restart = prop(row.props.restart, DEFAULT_RESTART)
    # The program is loaded inside its own bracket and run outside it: the
    # atomicity pass does not descend through an Eval, so a bracket placed
    # around the whole thing would hold storage open for as long as the
    # program runs. What the program itself touches is the program's to
    # bracket.
    load = nustd.kv.auto_flow_atomic(
        row.prog.load(scope={"plane": plane, "cell": cell}), scope=root
    )
    # ParallelAsync is how a term says "on the loop". A Cell that subscribes
    # to anything is async only, and an Eval placed off the loop refuses to
    # host one.
    run = nu.ParallelAsync(nu.prog.Eval(load))
    # Last run's error goes before this one starts, or a Cell that was fixed
    # still reads failed off a stale leaf. Written empty rather than erased:
    # every turn of every Cell would otherwise ask a leaf that is usually not
    # there whether it is, and asking that across the Navigator socket costs
    # a round trip and a reported miss each time.
    clear = row.error.set(nu.Str(""))
    # Guarded, because a write under a deleted Cell vivifies the row again
    # and the Space would grow a Cell that is nothing but a complaint.
    report = nu.IfDo(cells.contains(cell), row.error.set(nu.ToStr(nu.AttrRef("error"))))
    ended = nu.SetCmd(_attempt(), nu.Int(0)) >> nu.SwitchDo(
        restart, {RESTART_ALWAYS: _backoff()}, park()
    )
    raised = nu.SwitchDo(
        restart, {RESTART_ALWAYS: _backoff(), RESTART_ON_FAILURE: _backoff()}, park()
    )
    return nu.Let(
        _ATTEMPT_ATTR,
        nu.Int(0),
        body=nu.ForeverDo(
            nu.SetCmd(_attempt(), _attempt() + nu.Int(1))
            # A delete wakes this arm before the fold cancels it, so the turn
            # after one lands is a turn with no Cell to load. Read per turn,
            # not trusted from fan out.
            >> nu.IfDo(
                cells.contains(cell),
                nu.TryCatch(clear >> run >> ended, catch=report >> raised),
                park(),
            )
        ),
    )


def _reloads(plane: nu.StrArg, body: nu.Nu, *, root: type[nu.Shape]) -> nu.Nu:
    """``body``, run again from the store whenever this Cell's program changes.

    The subscription is on ``prog`` and nothing wider. A Cell writing its own
    state, and nuspace writing the Cell's error, both sit elsewhere under the
    Cell, so neither can restart the thing that wrote them.
    """
    cell = nu.StrAttrRef(CELL_ATTR)
    row = root.planes[plane].cells[cell]
    return reenters_on(
        row.prog.on_change(),
        body,
        when=prop(row.props.reload, DEFAULT_RELOAD),
    )


def cell_arm(plane: nu.StrArg, *, root: type[nu.Shape] = Space) -> nu.Nu:
    """One Cell as an arm of an ``async`` Plane, reloading in place.

    Runs in the Plane's worker, beside its siblings. An edit cancels this arm
    and loads the program again in the process that is already up, which
    costs nothing the siblings can see.

    Args:
        plane: the Plane this Cell is in.
        root: the Space shape class this Cell is stored under.
    """
    return _reloads(plane, cell_body(plane, root=root), root=root)


def cell_dispatch(plane: nu.StrArg, *, root: type[nu.Shape] = Space) -> nu.Nu:
    """One Cell in a worker of its own, reloading by relaunch. The ``mp`` arm.

    Runs in the main process and holds a worker open for as long as the arm
    lives. The worker is killed on every way out: an edit, the Cell being
    deleted, the Plane stopping, the Space closing. A Cell that owns a
    process gets a clean one when its code changes, which is the difference
    ``mp`` is for.

    The body is bracketed for atomicity here, before the ``Dispatch`` is
    built, because a dispatched body is payload and no pass reaches it.

    Args:
        plane: the Plane this Cell is in.
        root: the Space shape class this Cell is stored under.
    """
    cell = nu.StrAttrRef(CELL_ATTR)
    cells = root.planes[plane].cells
    pool = nustd.mp_pool.PoolRef()
    worker = nu.IntAttrRef(_WORKER_ATTR)
    body = nustd.kv.auto_flow_atomic(cell_body(plane, root=root), scope=root)
    held = nu.Let(
        _WORKER_ATTR,
        pool.launch(),
        # Dispatch returns as soon as the child has the body, so the park is
        # what holds the worker open. The kill runs on every exit, including
        # the cancellation the fold delivers when the Cell is deleted.
        body=nu.TryCatch(
            pool.dispatch(body, worker, carry=True) >> park(),
            finally_=pool.kill(worker),
        ),
    )
    report = nu.IfDo(cells.contains(cell), cells[cell].error.set(nu.ToStr(nu.AttrRef("error"))))
    # A worker that will not come up is this Cell's failure and is written to
    # its row. Then the arm waits: nothing here retries a launch, and a Cell
    # stays failed until its program changes.
    guarded = nu.TryCatch(held, catch=report >> park())
    return _reloads(plane, guarded, root=root)
